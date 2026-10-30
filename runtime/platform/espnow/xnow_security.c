#include "xnow_security.h"
#include "../../native/sha256.h"
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int overlap(const void *a,size_t n,const void *b,size_t m){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x<=y?y-x<n:x-y<m;}
static int unicast(const uint8_t a[6]){unsigned any=0;for(unsigned i=0;i<6;i++)any|=a[i];return any&&!(a[0]&1);}
static void derive_rx_scope(uint8_t out[32],const uint8_t local[6],const uint8_t peer[6],const uint8_t key[16]){
 static const uint8_t domain[]="X1000-CCMP-RX-PN-v1";struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,domain,sizeof(domain)-1);hb_sha256_update(&h,local,6);hb_sha256_update(&h,peer,6);hb_sha256_update(&h,key,16);hb_sha256_final(&h,out);wipe(&h,sizeof(h));
}
int xnow_security_rx_scope(uint8_t out[32],const uint8_t local[6],const uint8_t peer[6],const uint8_t key[16]){if(!out||!local||!peer||!key||!unicast(local)||!unicast(peer))return XNOW_SECURITY_ARGUMENT;derive_rx_scope(out,local,peer,key);return 0;}
int xnow_security_init(struct xnow_security *out,const struct xnow_security_io *io,const uint8_t local[6],const uint8_t peer[6],const uint8_t lmk[16],unsigned id,unsigned block){
 if(!out||!io||!io->reserve_tx||!io->load_rx||!io->commit_rx||!local||!peer||!lmk||!unicast(local)||!unicast(peer)||id>3)return XNOW_SECURITY_ARGUMENT;
 struct xnow_security s;memset(&s,0,sizeof(s));s.io=*io;s.key_id=id;memcpy(s.local,local,6);memcpy(s.peer,peer,6);memcpy(s.key,lmk,16);derive_rx_scope(s.rx_scope,local,peer,lmk);
 if(xnow_pn_init(&s.tx,local,lmk,block,io->context,io->reserve_tx)){wipe(&s,sizeof(s));return XNOW_SECURITY_ARGUMENT;}
 if(io->load_rx(io->context,s.rx_scope,&s.rx_highest)||s.rx_highest>XNOW_PN_LIMIT){wipe(&s,sizeof(s));return XNOW_SECURITY_STORAGE;}
 *out=s;wipe(&s,sizeof(s));return 0;
}
void xnow_security_clear(struct xnow_security *s){if(s)wipe(s,sizeof(*s));}
int xnow_security_init_espnow(struct xnow_security *s,const struct xnow_security_io *io,const uint8_t local[6],const uint8_t peer[6],const uint8_t wire_key[16],unsigned block){
 int r=xnow_security_init(s,io,local,peer,wire_key,3,block);if(!r)s->espnow_profile=1;return r;
}
int xnow_security_seal(struct xnow_security *s,unsigned version,const uint8_t random[4],const void *data,size_t n,uint8_t *out,size_t capacity,size_t *written){
 if(!s||!random||!out||!written||!s->tx.reserve)return XNOW_SECURITY_ARGUMENT;
 size_t span=capacity<XNOW_CCMP_FRAME_MAX?capacity:XNOW_CCMP_FRAME_MAX;
 if(overlap(s,sizeof(*s),out,span)||overlap(s,sizeof(*s),written,sizeof(*written))||overlap(out,span,written,sizeof(*written)))return XNOW_SECURITY_ARGUMENT;
 if(s->fault)return XNOW_SECURITY_UNCERTAIN;
 uint8_t plain[XNOW_ESPNOW_ACTION_MAX];size_t bytes=0;
 int r=xnow_espnow_encode_action(plain,sizeof(plain),s->peer,s->local,0,version,random,data,n,&bytes);
 if(r){wipe(plain,sizeof(plain));return XNOW_SECURITY_FORMAT;}
 if(capacity<bytes+16){wipe(plain,sizeof(plain));return XNOW_SECURITY_CAPACITY;}
 uint64_t pn;r=xnow_pn_next(&s->tx,&pn);
 if(r){s->fault=1;wipe(plain,sizeof(plain));return XNOW_SECURITY_STORAGE;}
 r=s->espnow_profile?xnow_ccmp_espnow_seal(s->key,s->key_id,pn,plain,bytes,out,capacity,written):xnow_ccmp_seal(s->key,s->key_id,pn,plain,bytes,out,capacity,written);wipe(plain,sizeof(plain));return r?XNOW_SECURITY_FORMAT:0;
}
int xnow_security_open(struct xnow_security *s,const uint8_t *frame,size_t n,void *out,size_t capacity,struct xnow_wire_info *info){
 if(!s||!frame||!info||(!out&&capacity)||!s->io.commit_rx)return XNOW_SECURITY_ARGUMENT;
 size_t span=capacity<XNOW_ESPNOW_V2_MAX?capacity:XNOW_ESPNOW_V2_MAX;
 if((out&&overlap(s,sizeof(*s),out,span))||overlap(s,sizeof(*s),info,sizeof(*info))||(out&&overlap(out,span,info,sizeof(*info))))return XNOW_SECURITY_ARGUMENT;
 if(s->fault)return XNOW_SECURITY_UNCERTAIN;
 if(n<40||memcmp(frame+4,s->local,6)||memcmp(frame+10,s->peer,6))return XNOW_SECURITY_FORMAT;
 uint8_t plain[XNOW_ESPNOW_ACTION_MAX],data[XNOW_ESPNOW_V2_MAX];size_t bytes=0;uint64_t highest=s->rx_highest;struct xnow_action_info found;
 int r=s->espnow_profile?xnow_ccmp_espnow_open(s->key,s->key_id,&highest,frame,n,plain,sizeof(plain),&bytes):xnow_ccmp_open(s->key,s->key_id,&highest,frame,n,plain,sizeof(plain),&bytes);
 if(r){wipe(plain,sizeof(plain));return r==XNOW_CCMP_REPLAY?XNOW_SECURITY_REPLAY:r==XNOW_CCMP_AUTH?XNOW_SECURITY_AUTH:XNOW_SECURITY_FORMAT;}
 r=xnow_espnow_decode_action(plain,bytes,data,sizeof(data),&found);wipe(plain,sizeof(plain));
 if(r){wipe(data,sizeof(data));return XNOW_SECURITY_FORMAT;}
 if(found.body.payload_bytes>capacity){wipe(data,sizeof(data));return XNOW_SECURITY_CAPACITY;}
 if(s->io.commit_rx(s->io.context,s->rx_scope,highest)){s->fault=1;wipe(data,sizeof(data));return XNOW_SECURITY_STORAGE;}
 s->rx_highest=highest;
 if(found.body.payload_bytes)memcpy(out,data,found.body.payload_bytes);
 *info=found.body;wipe(data,sizeof(data));return 0;
}
