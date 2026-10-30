#include "../runtime/platform/espnow/xnow_security.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct durable {uint8_t scope[32];uint64_t high;};static struct durable records[16];static unsigned used,commits;static int reserve_fail,commit_fail,load_fail;
static struct durable *record(const uint8_t scope[32]){for(unsigned i=0;i<used;i++)if(!memcmp(records[i].scope,scope,32))return &records[i];assert(used<16);struct durable *p=&records[used++];memcpy(p->scope,scope,32);p->high=0;return p;}
static int reserve(void *unused,const uint8_t scope[32],unsigned n,uint64_t *first,uint64_t *last){(void)unused;struct durable *p=record(scope);*first=p->high+1;p->high+=n;*last=p->high;return reserve_fail?-1:0;}
static int load(void *unused,const uint8_t scope[32],uint64_t *high){(void)unused;if(load_fail)return -1;*high=record(scope)->high;return 0;}
static int commit(void *unused,const uint8_t scope[32],uint64_t high){(void)unused;commits++;struct durable *p=record(scope);if(high<=p->high)return -1;p->high=high;return commit_fail?-1:0;}
int main(void){
 struct xnow_security_io io={0,reserve,load,commit};struct xnow_security a,b,restarted,other;
 uint8_t ma[6]={2,1,2,3,4,5},mb[6]={2,6,7,8,9,10},mc[6]={2,11,12,13,14,15},key[16]={0},random[4]={1,2,3,4};
 assert(!xnow_security_init(&a,&io,ma,mb,key,0,1024)&&!xnow_security_init(&b,&io,mb,ma,key,0,1024));
 uint8_t payload[1470],frame[1560],decoded[1470];for(unsigned i=0;i<sizeof(payload);i++)payload[i]=(uint8_t)(i*17);
 size_t bytes=0;struct xnow_wire_info info;
 /* Separate compatibility gate: an otherwise authenticated generic CCMP
  * vector with wire Key ID3 is rejected by a context configured for ID0.
  * This synthetic vector is not an Espressif RF capture/profile oracle. */
 uint8_t id_plain[XNOW_ESPNOW_ACTION_MAX];size_t id_bytes;
 assert(!xnow_espnow_encode_action(id_plain,sizeof(id_plain),mb,ma,0,1,random,payload,10,&id_bytes));
 assert(!xnow_ccmp_seal(key,3,1,id_plain,id_bytes,frame,sizeof(frame),&bytes));
 unsigned id_commits=commits;memset(decoded,0xa5,sizeof(decoded));
 assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_FORMAT&&commits==id_commits&&decoded[0]==0xa5&&!b.rx_highest);
 assert(!xnow_security_seal(&a,2,random,payload,sizeof(payload),frame,sizeof(frame),&bytes)&&bytes==1560);
 memset(decoded,0xa5,sizeof(decoded));unsigned before=commits;
 assert(xnow_security_open(&b,frame,bytes,decoded,1,&info)==XNOW_SECURITY_CAPACITY&&commits==before&&decoded[0]==0xa5);
 assert(!xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)&&!memcmp(decoded,payload,sizeof(payload))&&info.payload_bytes==1470);
 assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 uint8_t reverse[1560];size_t reverse_bytes;assert(!xnow_security_seal(&b,1,random,payload,10,reverse,sizeof(reverse),&reverse_bytes));
 assert(!xnow_security_open(&a,reverse,reverse_bytes,decoded,sizeof(decoded),&info)&&info.payload_bytes==10);
 assert(xnow_security_open(&a,reverse,reverse_bytes,&a,sizeof(a),&info)==XNOW_SECURITY_ARGUMENT);

 assert(!xnow_security_init(&restarted,&io,mb,ma,key,0,1024));assert(xnow_security_open(&restarted,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 assert(!xnow_security_init(&other,&io,ma,mc,key,0,1024));assert(!memcmp(a.tx.scope,other.tx.scope,32));
 assert(!xnow_security_seal(&other,1,random,payload,10,frame,sizeof(frame),&bytes));uint64_t pn=frame[24]|((uint64_t)frame[25]<<8);assert(pn==1025);
 assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_FORMAT);
 assert(!xnow_security_seal(&a,1,random,payload,10,frame,sizeof(frame),&bytes));frame[bytes-1]^=1;before=commits;
 assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_AUTH&&commits==before);frame[bytes-1]^=1;
 commit_fail=1;memset(decoded,0xa5,sizeof(decoded));assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_STORAGE&&decoded[0]==0xa5&&b.fault);commit_fail=0;
 assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_UNCERTAIN);
 assert(!xnow_security_init(&b,&io,mb,ma,key,0,1024));assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 assert(!xnow_security_init(&a,&io,ma,mb,key,0,1024));reserve_fail=1;bytes=999;
 assert(xnow_security_seal(&a,1,random,payload,10,frame,sizeof(frame),&bytes)==XNOW_SECURITY_STORAGE&&bytes==999&&a.fault);reserve_fail=0;
 load_fail=1;assert(xnow_security_init(&a,&io,ma,mb,key,0,1024)==XNOW_SECURITY_STORAGE);load_fail=0;
 xnow_security_clear(&a);xnow_security_clear(&b);for(unsigned i=0;i<sizeof(a);i++)assert(((uint8_t *)&a)[i]==0);
 puts("Security context: PN reservation, two-way identity binding, maximum payload, restart replay, shared-key namespaces and durable-commit-before-output passed; storage callbacks modeled.");return 0;
}
