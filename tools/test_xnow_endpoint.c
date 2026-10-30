/* Reuse the synthetic word-command endpoint, exercising the real full backend. */
#define main full_backend_checks
#include "test_xnow_full.c"
#undef main
#include "../runtime/platform/espnow/xnow_endpoint.h"
static int rng_fail;static unsigned rng_calls;
static int random_bytes(void *context,uint8_t bytes[4]){(void)context;rng_calls++;if(rng_fail)return -1;for(unsigned i=0;i<4;i++)bytes[i]=(uint8_t)(rng_calls+i);return 0;}
int main(void){
 assert(full_backend_checks()==0);
 reset();struct xnow_full s;struct xnow_endpoint endpoint;struct xnow_endpoint_result event;
 assert(!xnow_full_open(&s,&io,&layout));assert(!xnow_endpoint_init(&endpoint,&s,6,7,0,random_bytes));
 struct xnow_peer a={{2,0,0,0,0,1},{0},0,1,0},b={{2,0,0,0,0,2},{0},6,2,0};
 assert(!xnow_endpoint_add(&endpoint,&a)&&!xnow_endpoint_add(&endpoint,&b));
 unsigned char payload[251];memset(payload,0x55,sizeof(payload));
 assert(xnow_endpoint_send(&endpoint,0,payload,251)==XNOW_ENDPOINT_LENGTH&&!submits&&!allocations);
 b.channel=1;assert(!xnow_endpoint_modify(&endpoint,&b));assert(xnow_endpoint_send(&endpoint,0,payload,10)==XNOW_ENDPOINT_CHANNEL&&!submits);
 b.channel=6;b.encrypt=1;memset(b.lmk,0xa5,16);assert(!xnow_endpoint_modify(&endpoint,&b));
 assert(xnow_endpoint_send(&endpoint,0,payload,10)==XNOW_ENDPOINT_CRYPTO_UNAVAILABLE&&!submits);
 b.encrypt=0;assert(!xnow_endpoint_modify(&endpoint,&b));
 assert(!xnow_endpoint_send(&endpoint,0,payload,10));memset(payload,0xff,sizeof(payload));
 assert(xnow_endpoint_delete(&endpoint,a.address)==XNOW_PENDING);
 rng_fail=1;assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_IO&&!submits);rng_fail=0;
 assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING&&submits==1);
 assert(packet[8]==0x34fe187f); /* body at32 starts category/OUI, no app prefix */
 unsigned char decoded[250];struct xnow_wire_info info;assert(!xnow_espnow_decode_body((unsigned char *)packet+32,*at(layout.tx+20),decoded,sizeof(decoded),&info));assert(decoded[0]==0x55&&info.payload_bytes==10);
 assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING&&submits==1);
 done(0);assert(!xnow_endpoint_poll(&endpoint,&event)&&!memcmp(event.destination,a.address,6)&&event.stock_status==0);
 assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING&&submits==2);
 done(1);assert(!xnow_endpoint_poll(&endpoint,&event)&&!memcmp(event.destination,b.address,6)&&event.stock_status==1);
 assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_AGAIN&&!endpoint.active);
 for(unsigned i=0;i<sizeof(endpoint.payload);i++)assert(endpoint.payload[i]==0);
 struct xnow_peer secure={{2,0x66,0x77,0x88,0x99,0xaa},{0},0,2,1};
 memset(secure.lmk,0x5a,16);assert(!xnow_endpoint_add(&endpoint,&secure));
 receive(payload,10);unsigned char received[250];memset(received,0xa5,sizeof(received));struct xnow_full_received received_info;
 assert(xnow_endpoint_receive(&endpoint,received,sizeof(received),&received_info)==XNOW_ENDPOINT_CRYPTO_UNAVAILABLE&&received[0]==0xa5);
 receive(payload,10);uint32_t broadcast_slot=layout.rx+24+(*at(layout.rx+8)&1)*16;*at(broadcast_slot+12)|=0x20000u;
 assert(!xnow_endpoint_receive(&endpoint,received,sizeof(received),&received_info)&&received_info.flags==XNOW_RX_BROADCAST);
 assert(!xnow_endpoint_delete(&endpoint,secure.address));
 receive(payload,10);assert(!xnow_endpoint_receive(&endpoint,received,sizeof(received),&received_info)&&received[0]==0xff);
 assert(!received_info.flags);
 assert(!xnow_endpoint_send(&endpoint,0,payload,10));assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING&&submits==3);
 assert(xnow_endpoint_stop_step(&endpoint)==XNOW_PENDING);
 assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING&&submits==3);done(0);
 assert(!xnow_endpoint_stop_step(&endpoint)&&submits==3);unsigned n,e;xnow_peer_count(&endpoint.peers,&n,&e);assert(!n&&!e);
 for(unsigned i=0;i<sizeof(endpoint.peers);i++)assert(((unsigned char *)&endpoint.peers)[i]==0);
 puts("Endpoint: atomic all-peer validation, data snapshot, serial completions, RNG failure, encrypted refusal and stop erasure passed.");return 0;
}
