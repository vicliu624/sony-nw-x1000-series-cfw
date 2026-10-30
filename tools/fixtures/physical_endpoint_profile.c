#define SECURE_ENDPOINT_MAIN old_endpoint_checks
#include "../test_xnow_endpoint_security.c"
#undef SECURE_ENDPOINT_MAIN
#include "physical_vector.private.h"
static void physical_incoming(const uint8_t *f,size_t n){
 memcpy(packet,f+24,n-24);uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;
 *at(slot)=PACKET;*at(slot+4)=n-24;
 *at(slot+8)=(uint32_t)f[10]|((uint32_t)f[11]<<8)|((uint32_t)f[12]<<16)|((uint32_t)f[13]<<24);
 *at(slot+12)=(uint32_t)f[14]|((uint32_t)f[15]<<8)|0x10000u;*at(layout.rx+4)=tail+1;
}
int main(void){
 assert(!native_backend_checks());reset();struct xnow_full transport;assert(!xnow_full_open(&transport,&io,&layout));
 struct xnow_endpoint endpoint;assert(!xnow_endpoint_init(&endpoint,&transport,8,17,0,random_bytes));
 struct xnow_security_io storage={0,reserve,load,commit};struct xnow_endpoint_security workspace;
 assert(!xnow_endpoint_security_attach_espnow(&endpoint,&workspace,captured+4,test_pmk,1024,&storage));
 struct xnow_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,captured+10,6);memcpy(peer.lmk,test_lmk,16);peer.version=2;peer.encrypt=1;assert(!xnow_endpoint_add(&endpoint,&peer));
 uint8_t data[1470];struct xnow_full_received info;physical_incoming(captured,sizeof captured);
 assert(!xnow_endpoint_receive(&endpoint,data,sizeof data,&info)&&info.flags==XNOW_RX_AUTHENTICATED&&info.info.payload_bytes==sizeof expected_payload&&!memcmp(data,expected_payload,sizeof expected_payload));
 unsigned before=commits;physical_incoming(captured,sizeof captured);assert(xnow_endpoint_receive(&endpoint,data,sizeof data,&info)==XNOW_SECURITY_REPLAY&&commits==before);
 assert(!xnow_endpoint_modify(&endpoint,&peer));physical_incoming(captured,sizeof captured);assert(xnow_endpoint_receive(&endpoint,data,sizeof data,&info)==XNOW_SECURITY_REPLAY);
 for(unsigned i=0;i<sizeof data;i++)data[i]=(uint8_t)(i*19u);
 assert(!xnow_endpoint_send(&endpoint,peer.address,data,sizeof data));struct xnow_endpoint_result result;assert(xnow_endpoint_poll(&endpoint,&result)==XNOW_PENDING);
 assert(((uint8_t *)packet)[35]==0xe0);
 uint8_t frame[1560];memset(frame,0,24);frame[0]=0xd0;frame[1]=0x40;memcpy(frame+4,peer.address,6);memcpy(frame+10,captured+4,6);memset(frame+16,255,6);
 size_t bytes=*at(layout.tx+20);assert(bytes==1536);memcpy(frame+24,(uint8_t *)packet+32,bytes);
 puts("ESP_TX_FRAME");for(unsigned i=0;i<24+bytes;i++)printf("%02x",frame[i]);puts("");
 done(0);assert(!xnow_endpoint_poll(&endpoint,&result)&&!result.result);
 assert(!xnow_endpoint_stop_step(&endpoint));for(unsigned i=0;i<sizeof workspace;i++)assert(((uint8_t *)&workspace)[i]==0);
 puts("Measured endpoint profile: physical RX authentication, replay after context reset,1470 encrypted submit and PMK/workspace erase passed; IO storage modeled.");return 0;
}
