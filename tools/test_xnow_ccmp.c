#include "../runtime/platform/espnow/xnow_ccmp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ccmp_vectors.h"
int main(void){
 uint8_t plain[1544],encrypted[1560],decoded[1544],bad[1560];size_t n;
 for(unsigned v=0;v<sizeof(vectors)/sizeof(vectors[0]);v++){
  const struct vector *p=&vectors[v];memcpy(plain,header,24);for(unsigned i=0;i<p->bytes;i++)plain[24+i]=(uint8_t)(i*17+3);
  memset(encrypted,0xa5,sizeof(encrypted));n=999;
  assert(!xnow_ccmp_seal(key,0,p->pn,plain,24+p->bytes,encrypted,sizeof(encrypted),&n));assert(n==40+p->bytes&&!memcmp(encrypted,p->frame,n));
  uint64_t highest=0;size_t length=999;assert(!xnow_ccmp_open(key,0,&highest,encrypted,n,decoded,sizeof(decoded),&length));
  assert(highest==p->pn&&length==24+p->bytes&&!memcmp(decoded,plain,length));
  memset(decoded,0xa5,sizeof(decoded));length=999;
  assert(xnow_ccmp_open(key,0,&highest,encrypted,n,decoded,sizeof(decoded),&length)==XNOW_CCMP_REPLAY&&length==999&&decoded[0]==0xa5);
  for(unsigned i=0;i<3;i++){
   memcpy(bad,encrypted,n);bad[i==0?n-1:i==1?15:32]^=0x80;highest=0;length=999;
   assert(xnow_ccmp_open(key,0,&highest,bad,n,decoded,sizeof(decoded),&length)==XNOW_CCMP_AUTH&&highest==0&&length==999&&decoded[0]==0xa5);
  }
  memcpy(bad,encrypted,n);bad[26]=1;highest=0;assert(xnow_ccmp_open(key,0,&highest,bad,n,decoded,sizeof(decoded),&length)==XNOW_CCMP_FORMAT);
  highest=0;assert(xnow_ccmp_open(key,1,&highest,encrypted,n,decoded,sizeof(decoded),&length)==XNOW_CCMP_FORMAT);
  assert(xnow_ccmp_open(key,0,&highest,encrypted,n,decoded,1,&length)==XNOW_CCMP_CAPACITY&&highest==0);
  assert(xnow_ccmp_seal(key,0,0,plain,24+p->bytes,encrypted,sizeof(encrypted),&n)==XNOW_CCMP_ARGUMENT);
  assert(xnow_ccmp_seal(key,0,p->pn,plain,24+p->bytes,plain,sizeof(plain),&n)==(p->bytes==1520?XNOW_CCMP_CAPACITY:XNOW_CCMP_ALIAS));
 }
 puts("CCMP: independent AES-CCM vectors, maximum body, MIC/header/cipher tamper, replay, key ID, capacity and alias checks passed; no ESP over-air claim.");return 0;
}
