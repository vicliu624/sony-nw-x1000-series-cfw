#define main native_backend_checks
#include "test_xnow_full.c"
#undef main
#include "../runtime/platform/espnow/xnow_endpoint_security.h"
struct durable {uint8_t scope[32];uint64_t high;};static struct durable records[16];static unsigned used,commits;
static struct durable *record(const uint8_t scope[32]){for(unsigned i=0;i<used;i++)if(!memcmp(records[i].scope,scope,32))return &records[i];assert(used<16);struct durable *p=&records[used++];memcpy(p->scope,scope,32);return p;}
static int reserve(void *unused,const uint8_t scope[32],unsigned n,uint64_t *first,uint64_t *last){(void)unused;struct durable *p=record(scope);*first=p->high+1;p->high+=n;*last=p->high;return 0;}
static int load(void *unused,const uint8_t scope[32],uint64_t *high){(void)unused;*high=record(scope)->high;return 0;}
static int commit(void *unused,const uint8_t scope[32],uint64_t high){(void)unused;struct durable *p=record(scope);if(high<=p->high)return -1;p->high=high;commits++;return 0;}
static int random_bytes(void *unused,uint8_t r[4]){(void)unused;r[0]=1;r[1]=2;r[2]=3;r[3]=4;return 0;}
static void incoming(const uint8_t *frame,size_t bytes){
 memcpy(packet,frame+24,bytes-24);uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;
 unsigned flags=(frame[1]&0x40?1:0)|(frame[4]==255?2:0);
 *at(slot)=PACKET;*at(slot+4)=bytes-24;*at(slot+8)=0x03020102;*at(slot+12)=0x0504|(flags<<16);*at(layout.rx+4)=tail+1;
}
#ifndef SECURE_ENDPOINT_MAIN
#define SECURE_ENDPOINT_MAIN main
#endif
int SECURE_ENDPOINT_MAIN(void){
 assert(native_backend_checks()==0);reset();struct xnow_full transport;assert(!xnow_full_open(&transport,&io,&layout));
 struct xnow_endpoint endpoint;assert(!xnow_endpoint_init(&endpoint,&transport,6,7,0,random_bytes));
 struct xnow_security_io security_io={0,reserve,load,commit};struct xnow_endpoint_security workspace;
 uint8_t local[6]={2,6,7,8,9,10},remote[6]={2,1,2,3,4,5},key[16]={0};
 assert(!xnow_endpoint_security_attach(&endpoint,&workspace,local,1024,&security_io));
 struct xnow_peer peer={{2,1,2,3,4,5},{0},0,2,1};assert(!xnow_endpoint_add(&endpoint,&peer));
 uint8_t data[1470];for(unsigned i=0;i<sizeof(data);i++)data[i]=(uint8_t)i;
 assert(!xnow_endpoint_send(&endpoint,remote,data,sizeof(data)));struct xnow_endpoint_result event;
 assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING&&*at(layout.tx+16)==4);
 assert(((uint8_t *)packet)[32+3]==0x20);done(0);assert(!xnow_endpoint_poll(&endpoint,&event));
 struct xnow_security sender;assert(!xnow_security_init(&sender,&security_io,remote,local,key,0,1024));
 uint8_t frame[1560],out[1470],random[4]={1,2,3,4};size_t bytes;struct xnow_full_received info;
 assert(!xnow_security_seal(&sender,2,random,data,sizeof(data),frame,sizeof(frame),&bytes));incoming(frame,bytes);memset(out,0xa5,sizeof(out));
 unsigned before=commits;assert(xnow_endpoint_receive(&endpoint,out,1,&info)==XNOW_ARGUMENT&&workspace.received_bytes==1560&&commits==before&&out[0]==0xa5);
 assert(!xnow_endpoint_receive(&endpoint,out,sizeof(out),&info)&&!memcmp(out,data,sizeof(out))&&info.info.payload_bytes==1470&&!workspace.received_bytes&&commits==before+1);
 assert(info.flags==XNOW_RX_AUTHENTICATED);
 incoming(frame,bytes);assert(xnow_endpoint_receive(&endpoint,out,sizeof(out),&info)==XNOW_SECURITY_REPLAY);
 assert(!xnow_endpoint_modify(&endpoint,&peer));for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)assert(!workspace.used[i]);
 incoming(frame,bytes);assert(xnow_endpoint_receive(&endpoint,out,sizeof(out),&info)==XNOW_SECURITY_REPLAY); /* reload persisted RX floor */
 assert(!xnow_security_seal(&sender,1,random,data,10,frame,sizeof(frame),&bytes));frame[bytes-1]^=1;incoming(frame,bytes);before=commits;
 assert(xnow_endpoint_receive(&endpoint,out,sizeof(out),&info)==XNOW_SECURITY_AUTH&&commits==before);frame[bytes-1]^=1;
 assert(!xnow_endpoint_delete(&endpoint,endpoint.peers.peers[0].address));for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)assert(!workspace.used[i]);
 assert(!xnow_endpoint_add(&endpoint,&peer));incoming(frame,bytes);assert(!xnow_endpoint_receive(&endpoint,out,sizeof(out),&info));
 /* A peer's encrypted unicast relationship must not suppress its plaintext
  * broadcasts: multicast encryption is not supported by ESP-NOW. */
 uint8_t broadcast[6]={255,255,255,255,255,255};before=commits;
 assert(!xnow_espnow_encode_action(frame,sizeof(frame),broadcast,remote,0,2,random,data,251,&bytes));incoming(frame,bytes);
 assert(!xnow_endpoint_receive(&endpoint,out,sizeof(out),&info)&&info.info.payload_bytes==251&&!memcmp(out,data,251)&&commits==before);
 assert(info.flags==XNOW_RX_BROADCAST);
 /* Keep explicit plaintext-unicast downgrade rejection for encrypted peers. */
 assert(!xnow_espnow_encode_action(frame,sizeof(frame),local,remote,0,1,random,data,10,&bytes));incoming(frame,bytes);
 assert(xnow_endpoint_receive(&endpoint,out,sizeof(out),&info)==XNOW_ENDPOINT_CRYPTO_UNAVAILABLE&&commits==before);
 assert(!xnow_endpoint_stop_step(&endpoint));for(unsigned i=0;i<sizeof(workspace);i++)assert(((uint8_t *)&workspace)[i]==0);
 xnow_security_clear(&sender);puts("Secure endpoint: protected submit, full-body authentication, retained capacity retry, durable replay, replacement/deletion and stop erasure passed; radio/storage callbacks modeled.");return 0;
}
