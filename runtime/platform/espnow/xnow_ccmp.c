#include "xnow_ccmp.h"
#include <bearssl.h>
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int overlap(const void *a,size_t n,const void *b,size_t m){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x<=y?y-x<n:x-y<m;}
static int unicast(const uint8_t *a){unsigned any=0;for(unsigned i=0;i<6;i++)any|=a[i];return any&&!(a[0]&1);}
static int header_ok(const uint8_t *h,unsigned protected){
 if(h[0]!=0xd0||(h[1]&0xc7)!=(protected?0x40:0)||(h[22]&15)||!unicast(h+4)||!unicast(h+10))return 0;
 for(unsigned i=16;i<22;i++)if(h[i]!=255)return 0;
 return 1;
}
static void inputs(const uint8_t *header,uint64_t pn,uint8_t nonce[13],uint8_t aad[22],unsigned espnow){
 nonce[0]=espnow?0:0x10;memcpy(nonce+1,header+10,6);
 for(unsigned i=0;i<6;i++)nonce[7+i]=(uint8_t)(pn>>(40-i*8));
 aad[0]=espnow?(header[0]&0x8f):header[0];aad[1]=(header[1]&0xc7)|0x40;memcpy(aad+2,header+4,18);aad[20]=header[22]&15;aad[21]=0;
}
static int crypt(const uint8_t key[16],const uint8_t *header,uint64_t pn,uint8_t *data,size_t n,uint8_t tag[8],int encrypt,unsigned espnow){
 br_aes_ct_ctrcbc_keys aes;br_ccm_context ccm;uint8_t nonce[13],aad[22];inputs(header,pn,nonce,aad,espnow);
 br_aes_ct_ctrcbc_init(&aes,key,16);br_ccm_init(&ccm,&aes.vtable);
 int valid=br_ccm_reset(&ccm,nonce,sizeof(nonce),sizeof(aad),n,8);
 if(valid){br_ccm_aad_inject(&ccm,aad,sizeof(aad));br_ccm_flip(&ccm);br_ccm_run(&ccm,encrypt,data,n);if(encrypt)br_ccm_get_tag(&ccm,tag);else valid=br_ccm_check_tag(&ccm,tag);}
 wipe(&aes,sizeof(aes));wipe(&ccm,sizeof(ccm));wipe(nonce,sizeof(nonce));wipe(aad,sizeof(aad));return valid;
}
static int seal_profile(const uint8_t key[16],unsigned key_id,uint64_t pn,const uint8_t *plain,size_t n,uint8_t *out,size_t capacity,size_t *written,unsigned espnow){
 if(!key||!plain||!out||!written||key_id>3||!pn||pn>XNOW_CCMP_PN_MAX)return XNOW_CCMP_ARGUMENT;
 if(n<24||n>1544||!header_ok(plain,0))return XNOW_CCMP_FORMAT;
 if(capacity<n+16)return XNOW_CCMP_CAPACITY;
 if(overlap(plain,n,out,n+16)||overlap(key,16,out,n+16)||overlap(written,sizeof(*written),out,n+16))return XNOW_CCMP_ALIAS;
 uint8_t frame[XNOW_CCMP_FRAME_MAX];memcpy(frame,plain,24);frame[1]|=0x40;
 uint8_t *iv=frame+24;iv[0]=(uint8_t)pn;iv[1]=(uint8_t)(pn>>8);iv[2]=0;iv[3]=(uint8_t)(0x20|(key_id<<6));for(unsigned i=0;i<4;i++)iv[4+i]=(uint8_t)(pn>>(16+i*8));
 size_t bytes=n-24;memcpy(frame+32,plain+24,bytes);
 if(!crypt(key,frame,pn,frame+32,bytes,frame+32+bytes,1,espnow)){wipe(frame,sizeof(frame));return XNOW_CCMP_ARGUMENT;}
 memcpy(out,frame,n+16);*written=n+16;wipe(frame,sizeof(frame));return 0;
}
static int open_profile(const uint8_t key[16],unsigned key_id,uint64_t *highest,const uint8_t *frame,size_t n,uint8_t *out,size_t capacity,size_t *written,unsigned espnow){
 if(!key||!highest||!frame||!out||!written||key_id>3||*highest>XNOW_CCMP_PN_MAX)return XNOW_CCMP_ARGUMENT;
 if(n<40||n>XNOW_CCMP_FRAME_MAX||!header_ok(frame,1))return XNOW_CCMP_FORMAT;
 const uint8_t *iv=frame+24;if(iv[2]||(iv[3]&0x3f)!=0x20||(iv[3]>>6)!=key_id)return XNOW_CCMP_FORMAT;
 uint64_t pn=iv[0]|((uint64_t)iv[1]<<8);for(unsigned i=0;i<4;i++)pn|=(uint64_t)iv[4+i]<<(16+i*8);
 if(!pn||pn<=*highest)return XNOW_CCMP_REPLAY;
 if(capacity<n-16)return XNOW_CCMP_CAPACITY;
 if(overlap(frame,n,out,n-16)||overlap(key,16,out,n-16)||overlap(highest,sizeof(*highest),out,n-16)||overlap(written,sizeof(*written),out,n-16)||overlap(highest,sizeof(*highest),written,sizeof(*written)))return XNOW_CCMP_ALIAS;
 uint8_t plain[1544],tag[8];size_t bytes=n-40;memcpy(plain,frame,24);memcpy(plain+24,frame+32,bytes);memcpy(tag,frame+n-8,8);
 int valid=crypt(key,frame,pn,plain+24,bytes,tag,0,espnow);wipe(tag,sizeof(tag));
 if(!valid){wipe(plain,sizeof(plain));return XNOW_CCMP_AUTH;}
 plain[1]&=(uint8_t)~0x40;memcpy(out,plain,n-16);*written=n-16;*highest=pn;wipe(plain,sizeof(plain));return 0;
}
int xnow_ccmp_seal(const uint8_t key[16],unsigned id,uint64_t pn,const uint8_t *p,size_t n,uint8_t *o,size_t cap,size_t *written){return seal_profile(key,id,pn,p,n,o,cap,written,0);}
int xnow_ccmp_open(const uint8_t key[16],unsigned id,uint64_t *pn,const uint8_t *p,size_t n,uint8_t *o,size_t cap,size_t *written){return open_profile(key,id,pn,p,n,o,cap,written,0);}
int xnow_ccmp_espnow_seal(const uint8_t key[16],unsigned id,uint64_t pn,const uint8_t *p,size_t n,uint8_t *o,size_t cap,size_t *written){return seal_profile(key,id,pn,p,n,o,cap,written,1);}
int xnow_ccmp_espnow_open(const uint8_t key[16],unsigned id,uint64_t *pn,const uint8_t *p,size_t n,uint8_t *o,size_t cap,size_t *written){return open_profile(key,id,pn,p,n,o,cap,written,1);}
int xnow_ccmp_espnow_wire_key(const uint8_t pmk[16],const uint8_t api_lmk[16],uint8_t out[16]){
 if(!pmk||!api_lmk||!out)return XNOW_CCMP_ARGUMENT;
 br_aes_ct_cbcenc_keys aes;uint8_t block[16],iv[16]={0};memcpy(block,api_lmk,16);
 br_aes_ct_cbcenc_init(&aes,pmk,16);br_aes_ct_cbcenc_run(&aes,iv,block,16);memcpy(out,block,16);
 wipe(&aes,sizeof aes);wipe(block,sizeof block);wipe(iv,sizeof iv);return 0;
}
