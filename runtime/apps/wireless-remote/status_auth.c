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
 if(!out||!key||!wr_status_frame(input,bytes))return -1;
 const uint8_t *p=input;
 if(wr_auth_check(p+bytes-16,p,bytes-16,key))return -1;
 if(p[3]=='1')return wr_status_decode(out,input,WR_STATUS_BYTES);
 uint8_t canonical[WR_STATUS_BYTES]={0};memcpy(canonical,p,44);canonical[3]='1';
 const unsigned offsets[4]={44,109,365,621},limits[4]={64,255,255,255};
 size_t cursor=52;
 for(unsigned i=0;i<4;i++){
  unsigned n=p[44+i*2]|(unsigned)p[45+i*2]<<8;
  if(n>limits[i]||n>bytes-16-cursor)return -1;
  /* Embedded NUL would give two encodings for the same canonical string. */
  for(unsigned j=0;j<n;j++)if(!p[cursor+j])return -1;
  for(unsigned j=0;j<n;j++)canonical[offsets[i]+j]=p[cursor+j];cursor+=n;
 }
 return cursor!=bytes-16?-1:wr_status_decode(out,canonical,sizeof canonical);
}
int wr_status_frame(const void *input,size_t bytes){
 if(!input||bytes<4)return 0;const uint8_t *p=input;
 return (!memcmp(p,"WRS1",4)&&bytes==WR_SIGNED_STATUS_BYTES)||
  (!memcmp(p,"WRS2",4)&&bytes>=WR_COMPACT_STATUS_MIN&&bytes<=WR_SIGNED_STATUS_BYTES);
}
int wr_status_pack(void *output,size_t capacity,const struct wr_status *s,const uint8_t key[32]){
 if(!output||!key)return -1;
 uint8_t canonical[WR_STATUS_BYTES];if(wr_status_encode(canonical,sizeof canonical,s))return -1;
 const unsigned offsets[4]={44,109,365,621};unsigned lengths[4];size_t bytes=WR_COMPACT_STATUS_MIN;
 for(unsigned i=0;i<4;i++){lengths[i]=(unsigned)strlen((const char *)canonical+offsets[i]);bytes+=lengths[i];}
 if(bytes>=WR_SIGNED_STATUS_BYTES)
  return wr_status_sign(output,capacity,s,key)?-1:(int)WR_SIGNED_STATUS_BYTES;
 if(capacity<bytes)return -1;
 uint8_t *p=output;memcpy(p,canonical,44);p[3]='2';size_t cursor=52;
 for(unsigned i=0;i<4;i++){
  unsigned n=lengths[i];p[44+i*2]=(uint8_t)n;p[45+i*2]=(uint8_t)(n>>8);
  memcpy(p+cursor,canonical+offsets[i],n);cursor+=n;
 }
 return wr_auth_tag(p+cursor,p,cursor,key)?-1:(int)bytes;
}
int wr_heartbeat_sign(void *output,size_t bytes,uint64_t session,uint32_t sequence,uint32_t snapshot,const uint8_t key[32]){
 if(!output||bytes<WR_HEARTBEAT_BYTES||!session||!sequence||!snapshot||snapshot>sequence||!key)return -1;
 uint8_t *p=output;memcpy(p,"WRH1",4);
 for(unsigned i=0;i<8;i++)p[4+i]=(uint8_t)(session>>(8*i));
 for(unsigned i=0;i<4;i++)p[12+i]=(uint8_t)(sequence>>(8*i));
 for(unsigned i=0;i<4;i++)p[16+i]=(uint8_t)(snapshot>>(8*i));
 return wr_auth_tag(p+20,p,20,key);
}
int wr_heartbeat_verify(uint64_t *session,uint32_t *sequence,uint32_t *snapshot,const void *input,size_t bytes,const uint8_t key[32]){
 if(!session||!sequence||!snapshot||!input||!key||bytes!=WR_HEARTBEAT_BYTES)return -1;
 const uint8_t *p=input;if(memcmp(p,"WRH1",4)||wr_auth_check(p+20,p,20,key))return -1;
 uint64_t s=0;uint32_t q=0,r=0;
 for(unsigned i=0;i<8;i++)s|=(uint64_t)p[4+i]<<(8*i);
 for(unsigned i=0;i<4;i++)q|=(uint32_t)p[12+i]<<(8*i);
 for(unsigned i=0;i<4;i++)r|=(uint32_t)p[16+i]<<(8*i);
 if(!s||!q||!r||r>q)return -1;*session=s;*sequence=q;*snapshot=r;return 0;
}
