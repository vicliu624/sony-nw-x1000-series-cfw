#include "status_auth.h"
#include "../../native/sha256.h"
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *b=p;while(n--)*b++=0;}
static void tag(const uint8_t key[32],const uint8_t *wire,size_t bytes,uint8_t result[32]){
 struct hb_sha256 s;uint8_t pad[64],inner[32];
 memset(pad,0x36,sizeof pad);for(unsigned i=0;i<32;i++)pad[i]^=key[i];
 hb_sha256_init(&s);hb_sha256_update(&s,pad,64);hb_sha256_update(&s,wire,(unsigned)bytes);hb_sha256_final(&s,inner);
 memset(pad,0x5c,sizeof pad);for(unsigned i=0;i<32;i++)pad[i]^=key[i];
 hb_sha256_init(&s);hb_sha256_update(&s,pad,64);hb_sha256_update(&s,inner,32);hb_sha256_final(&s,result);
 wipe(&s,sizeof s);wipe(pad,sizeof pad);wipe(inner,sizeof inner);
}
int wr_auth_tag(uint8_t result[16],const void *input,size_t bytes,const uint8_t key[32]){
 if(!result||!input||!key||bytes>1470)return -1;uint8_t full[32];tag(key,input,bytes,full);memcpy(result,full,16);wipe(full,sizeof full);return 0;
}
int wr_auth_check(const uint8_t expected[16],const void *input,size_t bytes,const uint8_t key[32]){
 uint8_t result[16];if(!expected||wr_auth_tag(result,input,bytes,key))return -1;unsigned diff=0;
 for(unsigned i=0;i<16;i++)diff|=result[i]^expected[i];wipe(result,sizeof result);return diff?-1:0;
}
int wr_status_sign(void *output,size_t bytes,const struct wr_status *s,const uint8_t key[32]){
 if(!output||!key||bytes<WR_SIGNED_STATUS_BYTES)return -1;
 uint8_t *p=output,result[32];if(wr_status_encode(p,bytes,s))return -1;
 tag(key,p,WR_STATUS_BYTES,result);memcpy(p+WR_STATUS_BYTES,result,16);wipe(result,sizeof result);return 0;
}
int wr_status_verify(struct wr_status *out,const void *input,size_t bytes,const uint8_t key[32]){
 if(!out||!input||!key||bytes!=WR_SIGNED_STATUS_BYTES)return -1;
 const uint8_t *p=input;uint8_t result[32];tag(key,p,WR_STATUS_BYTES,result);unsigned diff=0;
 for(unsigned i=0;i<16;i++)diff|=result[i]^p[WR_STATUS_BYTES+i];wipe(result,sizeof result);
 return diff?-1:wr_status_decode(out,input,WR_STATUS_BYTES);
}
