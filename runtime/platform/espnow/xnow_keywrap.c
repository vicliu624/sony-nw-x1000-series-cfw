#include "xnow_keywrap.h"
#include <bearssl.h>
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
int xnow_keywrap(const uint8_t key[16],const uint8_t *plain,size_t n,uint8_t *out,size_t capacity,size_t *written){
 if(!key||!plain||!out||!written||(n!=16&&n!=24&&n!=32))return XNOW_KEYWRAP_ARGUMENT;
 if(capacity<n+8)return XNOW_KEYWRAP_CAPACITY;
 br_aes_ct_cbcenc_keys aes;br_aes_ct_cbcenc_init(&aes,key,16);
 uint8_t data[40],block[16],iv[16];memset(data,0xa6,8);memcpy(data+8,plain,n);unsigned count=(unsigned)n/8;
 for(unsigned j=0;j<6;j++)for(unsigned i=1;i<=count;i++){
  memcpy(block,data,8);memcpy(block+8,data+8*i,8);memset(iv,0,16);br_aes_ct_cbcenc_run(&aes,iv,block,16);
  unsigned t=count*j+i;memcpy(data,block,8);data[7]^=(uint8_t)t;memcpy(data+8*i,block+8,8);
 }
 memcpy(out,data,n+8);*written=n+8;wipe(&aes,sizeof(aes));wipe(data,sizeof(data));wipe(block,sizeof(block));wipe(iv,sizeof(iv));return 0;
}
int xnow_keyunwrap(const uint8_t key[16],const uint8_t *wrapped,size_t n,uint8_t *out,size_t capacity,size_t *written){
 if(!key||!wrapped||!out||!written||(n!=24&&n!=32&&n!=40))return XNOW_KEYWRAP_ARGUMENT;
 if(capacity<n-8)return XNOW_KEYWRAP_CAPACITY;
 br_aes_ct_cbcdec_keys aes;br_aes_ct_cbcdec_init(&aes,key,16);
 uint8_t data[40],block[16],iv[16];memcpy(data,wrapped,n);unsigned count=(unsigned)n/8-1;
 for(unsigned j=6;j-->0;)for(unsigned i=count;i;i--){
  memcpy(block,data,8);block[7]^=(uint8_t)(count*j+i);memcpy(block+8,data+8*i,8);memset(iv,0,16);br_aes_ct_cbcdec_run(&aes,iv,block,16);memcpy(data,block,8);memcpy(data+8*i,block+8,8);
 }
 unsigned mismatch=0;for(unsigned i=0;i<8;i++)mismatch|=data[i]^0xa6;
 if(!mismatch){memcpy(out,data+8,n-8);*written=n-8;}
 wipe(&aes,sizeof(aes));wipe(data,sizeof(data));wipe(block,sizeof(block));wipe(iv,sizeof(iv));return mismatch?XNOW_KEYWRAP_AUTH:0;
}
