#include "xnow_endpoint_security.h"
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int find(struct xnow_endpoint_security *s,const uint8_t a[6]){for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)if(s->used[i]&&!memcmp(s->contexts[i].peer,a,6))return (int)i;return -1;}
static int prepare(void *context,const struct xnow_peer *peer){
 struct xnow_endpoint_security *s=context;if(!s||!peer||!peer->encrypt)return XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;
 uint8_t key[16];if(s->espnow_profile){if(xnow_ccmp_espnow_wire_key(s->pmk,peer->lmk,key))return XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;}else memcpy(key,peer->lmk,16);
 int at=find(s,peer->address);
 if(at>=0){if(!memcmp(s->contexts[at].key,key,16)){wipe(key,sizeof key);return s->contexts[at].fault?XNOW_UNCERTAIN:0;}xnow_security_clear(&s->contexts[at]);s->used[at]=0;}
 if(at<0)for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)if(!s->used[i]){at=(int)i;break;}
 if(at<0){wipe(key,sizeof key);return XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;}
 int r=s->espnow_profile?xnow_security_init_espnow(&s->contexts[at],&s->io,s->local,peer->address,key,s->block):xnow_security_init(&s->contexts[at],&s->io,s->local,peer->address,key,0,s->block);wipe(key,sizeof key);if(!r)s->used[at]=1;return r;
}
static int send_frame(void *context,struct xnow_full *transport,const uint8_t address[6],unsigned version,const uint8_t random[4],const void *data,size_t n){
 struct xnow_endpoint_security *s=context;int at=find(s,address);if(at<0)return XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;
 uint8_t frame[XNOW_CCMP_FRAME_MAX];size_t bytes=0;
 int r=xnow_security_seal(&s->contexts[at],version,random,data,n,frame,sizeof(frame),&bytes);
 if(!r)r=xnow_full_send_protected(transport,s->local,frame,bytes);
 wipe(frame,sizeof(frame));return r;
}
static int receive_frame(void *context,struct xnow_full *transport,void *out,size_t n,struct xnow_full_received *info){
 struct xnow_endpoint_security *s=context;
 if(!s->received_bytes){int r=xnow_full_receive_action(transport,s->local,s->received,sizeof(s->received),&s->received_bytes);if(r)return r;}
 struct xnow_peer peer;int known=!xnow_peer_get(&s->endpoint->peers,s->received+10,&peer);int protected=(s->received[1]&0x40)!=0;
 struct xnow_full_received found;memset(&found,0,sizeof(found));memcpy(found.source,s->received+10,6);
 if(!memcmp(s->received+4,"\xff\xff\xff\xff\xff\xff",6))found.flags|=XNOW_RX_BROADCAST;
 uint8_t data[XNOW_ESPNOW_V2_MAX];int r=0;
 if(protected){
  if(!known||!peer.encrypt)r=XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;
  else if((r=prepare(s,&peer))==0){int at=find(s,peer.address);r=xnow_security_open(&s->contexts[at],s->received,s->received_bytes,data,n<sizeof(data)?n:sizeof(data),&found.info);}
 }else if(known&&peer.encrypt&&memcmp(s->received+4,"\xff\xff\xff\xff\xff\xff",6))r=XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;
 else {struct xnow_action_info action;r=xnow_espnow_decode_action(s->received,s->received_bytes,data,sizeof(data),&action);if(r)r=XNOW_SECURITY_FORMAT;else{found.info=action.body;if(found.info.payload_bytes>n)r=XNOW_SECURITY_CAPACITY;}}
 if(known)wipe(&peer,sizeof(peer));
 if(r==XNOW_SECURITY_CAPACITY){wipe(data,sizeof(data));return XNOW_ARGUMENT;}
 if(!r){if(protected)found.flags|=XNOW_RX_AUTHENTICATED;if(found.info.payload_bytes)memcpy(out,data,found.info.payload_bytes);*info=found;}
 wipe(data,sizeof(data));wipe(s->received,sizeof(s->received));s->received_bytes=0;return r;
}
static void forget(void *context,const uint8_t a[6]){
 struct xnow_endpoint_security *s=context;int at=find(s,a);if(at>=0){xnow_security_clear(&s->contexts[at]);s->used[at]=0;}
 if(s->received_bytes&&!memcmp(s->received+10,a,6)){wipe(s->received,sizeof(s->received));s->received_bytes=0;}
}
static void clear(void *context){struct xnow_endpoint_security *s=context;if(s)wipe(s,sizeof(*s));}
int xnow_endpoint_security_attach(struct xnow_endpoint *e,struct xnow_endpoint_security *s,const uint8_t local[6],unsigned block,const struct xnow_security_io *io){
 if(!e||!e->transport||!s||!local||!io||!io->reserve_tx||!io->load_rx||!io->commit_rx||!block||block>65536||e->crypto.context)return XNOW_ARGUMENT;
 unsigned count,encrypted;xnow_peer_count(&e->peers,&count,&encrypted);if(count||e->active||e->stopping)return XNOW_PENDING;
 unsigned any=0;for(unsigned i=0;i<6;i++)any|=local[i];if(!any||(local[0]&1))return XNOW_ARGUMENT;
 memset(s,0,sizeof(*s));s->endpoint=e;s->io=*io;s->block=block;memcpy(s->local,local,6);
 struct xnow_endpoint_crypto ops={s,prepare,send_frame,receive_frame,forget,clear};e->crypto=ops;return 0;
}
int xnow_endpoint_security_attach_espnow(struct xnow_endpoint *e,struct xnow_endpoint_security *s,const uint8_t local[6],const uint8_t pmk[16],unsigned block,const struct xnow_security_io *io){
 if(!pmk)return XNOW_ARGUMENT;
 uint8_t copy[16];memcpy(copy,pmk,16);int r=xnow_endpoint_security_attach(e,s,local,block,io);
 if(!r){memcpy(s->pmk,copy,16);s->espnow_profile=1;}wipe(copy,sizeof copy);return r;
}
