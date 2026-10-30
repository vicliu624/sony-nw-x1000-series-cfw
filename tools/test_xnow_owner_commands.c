#define main backend_checks
#include "test_xnow_full.c"
#undef main
#include "../runtime/platform/espnow/xnow_owner_commands.h"
static struct xnow_endpoint endpoint;static int available=1,stops;
static struct xnow_endpoint *ready(void *p){(void)p;return available?&endpoint:0;}
static void stop(void *p){(void)p;stops++;endpoint.stopping=1;}
static int random4(void *p,uint8_t b[4]){(void)p;memset(b,0x31,4);return 0;}
static void le(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(i*8));}
static int32_t result(const uint8_t *p){return (int32_t)((uint32_t)p[8]|(uint32_t)p[9]<<8|(uint32_t)p[10]<<16|(uint32_t)p[11]<<24);}
static size_t request(uint8_t *p,unsigned op,uint32_t token,unsigned n){memset(p,0,XNOW_OWNER_COMMAND_MAX);memcpy(p,"XNC1",4);p[4]=(uint8_t)op;le(p+8,token);le(p+12,n);return 16+n;}
#ifndef XNOW_OWNER_COMMAND_TEST_MAIN
#define XNOW_OWNER_COMMAND_TEST_MAIN main
#endif
int XNOW_OWNER_COMMAND_TEST_MAIN(void){
 assert(!backend_checks());reset();struct xnow_full full;assert(!xnow_full_open(&full,&io,&layout));assert(!xnow_endpoint_init(&endpoint,&full,6,17,0,random4));
 struct xnow_owner_commands c;assert(!xnow_owner_commands_init(&c,0,ready,stop));
 uint8_t command[XNOW_OWNER_COMMAND_MAX],reply[16],address[6]={2,1,2,3,4,5};
 size_t n=request(command,XNOW_OWNER_ADD,7,26);memcpy(command+16,address,6);command[22]=6;command[23]=2;
 assert(xnow_owner_commands_dispatch(&c,command,n,reply,15)==XNOW_ARGUMENT);unsigned total,encrypted;xnow_peer_count(&endpoint.peers,&total,&encrypted);assert(!total);
 assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&!result(reply)&&!memcmp(reply,"XNA1",4));xnow_peer_count(&endpoint.peers,&total,&encrypted);assert(total==1);
 command[25]=1;assert(xnow_owner_commands_dispatch(&c,command,n,reply,16)==XNOW_ARGUMENT);command[25]=0;
 n=request(command,XNOW_OWNER_SEND,123,6+1470);memcpy(command+16,address,6);for(unsigned i=0;i<1470;i++)command[22+i]=(uint8_t)i;
 assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&!result(reply));memset(command+22,0xff,1470);
 le(command+8,124);assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&result(reply)==XNOW_PENDING&&c.send_token==123);
 struct xnow_owner_completion event;memset(&event,0xa5,sizeof event);assert(xnow_owner_commands_poll(&c,&event)==XNOW_PENDING);
 uint8_t decoded[1470];struct xnow_wire_info wi;assert(!xnow_espnow_decode_body((uint8_t *)packet+32,*at(layout.tx+20),decoded,sizeof decoded,&wi));for(unsigned i=0;i<1470;i++)assert(decoded[i]==(uint8_t)i);
 done(1);assert(!xnow_owner_commands_poll(&c,&event)&&event.request==123&&event.result.stock_status==1&&!memcmp(event.result.destination,address,6));
 assert(xnow_owner_commands_poll(&c,&event)==XNOW_AGAIN&&!c.sending);
 receive(decoded,1470);uint8_t output[1470];struct xnow_full_received rx;assert(!xnow_owner_commands_receive(&c,output,sizeof output,&rx)&&!memcmp(decoded,output,1470));
 available=0;n=request(command,XNOW_OWNER_DELETE,8,6);memcpy(command+16,address,6);assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&result(reply)==XNOW_IDENTITY);xnow_peer_count(&endpoint.peers,&total,&encrypted);assert(total==1);
 assert(xnow_owner_commands_receive(&c,output,sizeof output,&rx)==XNOW_IDENTITY);available=1;
 n=request(command,XNOW_OWNER_SEND,9,6);command[5]=1;command[16]=1;assert(xnow_owner_commands_dispatch(&c,command,n,reply,16)==XNOW_ARGUMENT);command[16]=0;
 assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&!result(reply));assert(xnow_owner_commands_poll(&c,&event)==XNOW_PENDING);done(0);assert(!xnow_owner_commands_poll(&c,&event)&&event.request==9);assert(xnow_owner_commands_poll(&c,&event)==XNOW_AGAIN);
 n=request(command,XNOW_OWNER_MODIFY,10,26);memcpy(command+16,address,6);command[22]=6;command[23]=2;command[24]=1;memset(command+26,0x55,16);
 /* In-place reply cannot export any LMK in its16-byte response. */
 assert(!xnow_owner_commands_dispatch(&c,command,n,command,16)&&!result(command));xnow_peer_count(&endpoint.peers,&total,&encrypted);assert(encrypted==1);
 n=request(command,XNOW_OWNER_SEND,11,7);memcpy(command+16,address,6);command[22]=7;assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&result(reply)==XNOW_ENDPOINT_CRYPTO_UNAVAILABLE&&!c.sending);
 /* No plaintext fallback for encrypted peers lacking configured security. */
 n=request(command,XNOW_OWNER_STOP,12,0);assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&!result(reply)&&stops==1&&c.stopped);
 n=request(command,XNOW_OWNER_DELETE,13,6);memcpy(command+16,address,6);assert(!xnow_owner_commands_dispatch(&c,command,n,reply,16)&&result(reply)==XNOW_IDENTITY);assert(!xnow_endpoint_stop_step(&endpoint));
 puts("Full owner commands:1470 binary snapshot, reply backpressure, correlation, completion, RX, revoked access, encryption refusal, stop and malformed requests passed.");return 0;
}
