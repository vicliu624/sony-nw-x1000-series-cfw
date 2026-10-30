#include "espressif_ccmp_boundary.h"
#include "../../runtime/platform/espnow/xnow_ccmp.h"
#include "../../runtime/platform/espnow/xnow_wire.h"
#include <assert.h>
#include <stdio.h>
static uint8_t observed_nonce[13],observed_aad[30];static size_t observed_m,observed_bytes,observed_aad_bytes;static unsigned calls;
int aes_ccm_ad(const u8 *key,size_t key_bytes,const u8 *nonce,size_t m,const u8 *data,size_t n,const u8 *aad,size_t aad_bytes,const u8 *tag,u8 *plain){
 (void)key;(void)data;(void)tag;assert(key_bytes==16&&aad_bytes<=sizeof observed_aad);calls++;observed_m=m;observed_bytes=n;observed_aad_bytes=aad_bytes;memcpy(observed_nonce,nonce,13);memcpy(observed_aad,aad,aad_bytes);memset(plain,0,n);return 0;
}
int aes_ccm_ae(const u8 *key,size_t key_bytes,const u8 *nonce,size_t m,const u8 *plain,size_t n,const u8 *aad,size_t aad_bytes,u8 *crypt,u8 *tag){(void)key;(void)key_bytes;(void)nonce;(void)m;(void)plain;(void)n;(void)aad;(void)aad_bytes;(void)crypt;(void)tag;return -1;}
static void hex(const uint8_t *p,size_t n){for(size_t i=0;i<n;i++)printf("%02x",p[i]);}
int main(void){
 uint8_t frame[80],sealed[96],key[16]={0},source[6]={2,1,2,3,4,5},target[6]={2,6,7,8,9,10},random[4]={1,2,3,4};size_t bytes,encrypted;
 assert(!xnow_espnow_encode_action(frame,sizeof frame,target,source,0,1,random,0,0,&bytes));assert(bytes==39);assert(!xnow_ccmp_seal(key,0,0x010203040506ULL,frame,bytes,sealed,sizeof sealed,&encrypted));
 for(unsigned espnow=0;espnow<2;espnow++){
  size_t out_bytes=999;uint8_t *out=ccmp_decrypt(key,sealed,sealed+24,encrypted-24,&out_bytes,espnow!=0);assert(out&&out_bytes==15&&calls==espnow+1);free(out);
  assert(observed_m==(espnow?0u:8u)&&observed_nonce[0]==(espnow?0u:0x10u)&&observed_bytes==15&&observed_aad_bytes==22);
  assert(!memcmp(observed_nonce+1,source,6)&&!memcmp(observed_nonce+7,"\x01\x02\x03\x04\x05\x06",6));
  printf("CALL espnow=%u tag=%u nonce=",espnow,(unsigned)observed_m);hex(observed_nonce,13);printf(" aad=");hex(observed_aad,observed_aad_bytes);puts("");
 }
 printf("NATIVE ");hex(sealed,encrypted);puts("");
 puts("Upstream callback parameters captured only; no Espressif RF/MIC path or authentication result is established.");return 0;
}
