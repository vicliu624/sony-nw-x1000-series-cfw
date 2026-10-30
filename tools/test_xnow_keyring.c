#include "../runtime/platform/espnow/xnow_keyring.h"
#include "../runtime/platform/espnow/xnow_keywrap.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 uint8_t key[16],plain[32],wrapped[40],out[32],bad[40];for(unsigned i=0;i<16;i++){key[i]=(uint8_t)i;plain[i]=(uint8_t)(i*17);}
 const uint8_t expected[24]={0x1f,0xa6,0x8b,0x0a,0x81,0x12,0xb4,0x47,0xae,0xf3,0x4b,0xd8,0xfb,0x5a,0x7b,0x82,0x9d,0x3e,0x86,0x23,0x71,0xd2,0xcf,0xe5};size_t n;
 assert(!xnow_keywrap(key,plain,16,wrapped,sizeof(wrapped),&n)&&n==24&&!memcmp(wrapped,expected,24));
 for(unsigned length=16;length<=32;length+=8){for(unsigned i=0;i<length;i++)plain[i]=(uint8_t)(i*17+length);
  assert(!xnow_keywrap(key,plain,length,wrapped,sizeof(wrapped),&n)&&n==length+8);size_t bytes;
  assert(!xnow_keyunwrap(key,wrapped,n,out,sizeof(out),&bytes)&&bytes==length&&!memcmp(out,plain,length));
  for(unsigned i=0;i<n;i++){memcpy(bad,wrapped,n);bad[i]^=1;memset(out,0xa5,sizeof(out));bytes=999;assert(xnow_keyunwrap(key,bad,n,out,sizeof(out),&bytes)==XNOW_KEYWRAP_AUTH&&bytes==999&&out[0]==0xa5);}
  memcpy(out,plain,length);assert(!xnow_keywrap(key,out,length,wrapped,sizeof(wrapped),&bytes));assert(!xnow_keyunwrap(key,wrapped,n,wrapped,sizeof(wrapped),&bytes)&&!memcmp(wrapped,plain,length));
 }
 struct xnow_keyring ring;assert(!xnow_keyring_init(&ring,key));uint8_t address[6]={2,1,2,3,4,0};
 for(unsigned i=0;i<20;i++){address[5]=(uint8_t)i;memset(plain,(int)i,16);assert(!xnow_keyring_set(&ring,address,plain));}
 address[5]=20;assert(xnow_keyring_set(&ring,address,plain)==-3);address[5]=0;assert(!xnow_keyring_get(&ring,address,out)&&out[0]==0);
 uint8_t saved[32];memcpy(saved,ring.entries[0].wrapped,32);memcpy(ring.entries[0].wrapped,ring.entries[1].wrapped,32);
 memset(out,0xa5,sizeof(out));assert(xnow_keyring_get(&ring,address,out)==XNOW_KEYWRAP_AUTH&&out[0]==0xa5);memcpy(ring.entries[0].wrapped,saved,32);
 uint8_t next[16];memset(next,0x55,16);struct xnow_keyring before=ring;ring.entries[3].wrapped[0]^=1;struct xnow_keyring corrupt=ring;
 assert(xnow_keyring_rotate(&ring,next)==XNOW_KEYWRAP_AUTH&&!memcmp(&ring,&corrupt,sizeof(ring)));ring=before;
 assert(!xnow_keyring_rotate(&ring,next)&&!memcmp(ring.pmk,next,16)&&memcmp(ring.entries[0].wrapped,saved,32));
 for(unsigned i=0;i<20;i++){address[5]=(uint8_t)i;assert(!xnow_keyring_get(&ring,address,out)&&out[0]==i);}
 assert(!xnow_keyring_delete(&ring,ring.entries[0].address));for(unsigned i=0;i<sizeof(ring.entries[0]);i++)assert(((uint8_t *)&ring.entries[0])[i]==0);
 xnow_keyring_clear(&ring);for(unsigned i=0;i<sizeof(ring);i++)assert(((uint8_t *)&ring)[i]==0);
 assert(xnow_keyring_set(&ring,address,plain)==-1);
 puts("PMK/LMK local vault: RFC3394 known vector, tamper rejection, peer binding, rotation atomicity, limits and erasure passed; not an Espressif storage format.");return 0;
}
