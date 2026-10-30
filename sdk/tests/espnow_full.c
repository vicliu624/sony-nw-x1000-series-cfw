/* Public full-stack SDK consumer. Deterministic RAM callbacks, no device I/O. */
#include <x1000/services/espnow_endpoint.h>
#include <x1000/services/espnow_pn.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef SDK_FULL_SECURITY
#include <x1000/services/espnow_security.h>
#include <x1000/services/espnow_endpoint_security.h>
#include <x1000/services/espnow_keyring.h>
#endif
#ifdef SDK_FULL_DEVICE
#include <x1000/services/espnow_full_control.h>
#endif
static uint64_t upper;
static int reserve(void *ctx,const uint8_t scope[32],unsigned count,uint64_t *first,uint64_t *last){(void)ctx;(void)scope;*first=upper+1;upper+=count;*last=upper;return 0;}
static int random_bytes(void *ctx,uint8_t out[4]){(void)ctx;memset(out,1,4);return 0;}
#ifdef SDK_FULL_SECURITY
static int load(void *ctx,const uint8_t scope[32],uint64_t *highest){(void)ctx;(void)scope;*highest=0;return 0;}
static int commit(void *ctx,const uint8_t scope[32],uint64_t highest){(void)ctx;(void)scope;(void)highest;return 0;}
#endif
int main(void){
 struct xnow_full backend;memset(&backend,0,sizeof(backend));assert(xnow_full_open(&backend,0,0)==XNOW_ARGUMENT);
 struct xnow_endpoint endpoint;assert(!xnow_endpoint_init(&endpoint,&backend,6,7,0,random_bytes));
 struct xnow_peer peer={{2,1,2,3,4,5},{0},0,2,0};assert(!xnow_endpoint_add(&endpoint,&peer));
 uint8_t data[1470];memset(data,0x5a,sizeof(data));assert(!xnow_endpoint_send(&endpoint,peer.address,data,sizeof(data))); /* queue only */
 uint8_t local[6]={2,6,7,8,9,10},key[16]={0};struct xnow_pn pn;uint64_t value;
 assert(!xnow_pn_init(&pn,local,key,1024,0,reserve)&&!xnow_pn_next(&pn,&value)&&value==1);xnow_pn_clear(&pn);
#ifdef SDK_FULL_SECURITY
 struct xnow_security_io io={0,reserve,load,commit};struct xnow_security secure;assert(!xnow_security_init(&secure,&io,local,peer.address,key,0,1024));
 uint8_t frame[1560],nonce[4]={1,2,3,4};size_t bytes;assert(!xnow_security_seal(&secure,2,nonce,data,sizeof(data),frame,sizeof(frame),&bytes)&&bytes==1560);xnow_security_clear(&secure);
 uint8_t wire_key[16];static const uint8_t aes_zero[16]={0x66,0xe9,0x4b,0xd4,0xef,0x8a,0x2c,0x3b,0x88,0x4c,0xfa,0x59,0xca,0x34,0x2b,0x2e};
 assert(!xnow_ccmp_espnow_wire_key(key,key,wire_key)&&!memcmp(wire_key,aes_zero,16));
 assert(!xnow_security_init_espnow(&secure,&io,local,peer.address,wire_key,1024)&&secure.espnow_profile&&secure.key_id==3);
 assert(!xnow_security_seal(&secure,2,nonce,data,sizeof(data),frame,sizeof(frame),&bytes)&&bytes==1560&&frame[27]==0xe0);xnow_security_clear(&secure);
 struct xnow_endpoint measured;struct xnow_endpoint_security adapter;
 assert(!xnow_endpoint_init(&measured,&backend,6,7,0,random_bytes));
 assert(!xnow_endpoint_security_attach_espnow(&measured,&adapter,local,key,1024,&io)&&adapter.espnow_profile);
 measured.crypto.clear(measured.crypto.context);for(unsigned j=0;j<sizeof adapter;j++)assert(((uint8_t *)&adapter)[j]==0);
 struct xnow_keyring vault;assert(!xnow_keyring_init(&vault,key)&&!xnow_keyring_set(&vault,peer.address,key));uint8_t restored[16];assert(!xnow_keyring_get(&vault,peer.address,restored)&&!memcmp(key,restored,16));xnow_keyring_clear(&vault);
#endif
#ifdef SDK_FULL_DEVICE
 struct xnow_full_control controller;assert(xnow_full_control_init(&controller,0)==XNOW_ARGUMENT); /* no device open */
#endif
 puts("Public full ESP-NOW SDK consumer passed; no radio, network or filesystem access.");return 0;
}
