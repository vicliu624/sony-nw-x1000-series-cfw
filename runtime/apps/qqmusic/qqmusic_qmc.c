/* MIT License, Copyright (c) 2026 QM Unlock contributors.
 * C adaptation of the pinned qmunlock-derived PC reference. License retained
 * at third_party/qmc-reference/LICENSE; provenance in docs/apps/QQ_MUSIC.md. */
#include "qqmusic_qmc.h"
#include "qqmusic_protocol.h"
#include <string.h>
void qq_qmc_clear(struct qq_qmc_key *k) {if(k) qq_secret_clear(k,sizeof(*k));}
int qq_qmc_payload_length(uint64_t total,const unsigned char tail[16],uint64_t *bytes,int *footer) {
 uint32_t size;
 if(bytes) *bytes=0;
 if(footer) *footer=0;
 if(!tail||!bytes||!footer||total<16||total>268435456) return -1;
 if(memcmp(tail+8,"musicex\0",8)) {*bytes=total;return 0;}
 size=tail[0]|(uint32_t)tail[1]<<8|(uint32_t)tail[2]<<16|(uint32_t)tail[3]<<24;
 if(size<16||size>=total) return -1;
 *bytes=total-size;*footer=1;return 0;
}
int qq_qmc_init(struct qq_qmc_key *k,const unsigned char *key,size_t n) {
 unsigned i,j=0;uint32_t h=1;
 if(!k) return -1;
 qq_qmc_clear(k);
 if(!key||n<16||n>sizeof(k->key)) return -1;
 memcpy(k->key,key,n);k->length=(unsigned)n;
 for(i=0;i<n;i++) k->box[i]=(unsigned char)i;
 for(i=0;i<n;i++) {unsigned char v;j=(j+k->box[i]+key[i])%(unsigned)n;v=k->box[i];k->box[i]=k->box[j];k->box[j]=v;}
 for(i=0;i<n;i++) if(key[i]) {uint32_t next=h*key[i];if(!next||next<=h) break;h=next;}
 k->hash=h;return 0;
}
static unsigned skip(const struct qq_qmc_key *k,uint64_t id) {
 unsigned seed=k->key[id%k->length];
 return !seed?0:(unsigned)((uint64_t)(((double)k->hash/((double)(id+1)*seed))*100.0)%k->length);
}
static void rc4_segment(const struct qq_qmc_key *k,unsigned char *data,size_t n,uint64_t offset) {
 unsigned char box[2048];unsigned j=0,v=0;size_t done=0;
 uint64_t discard=offset%5120+skip(k,offset/5120);
 memcpy(box,k->box,k->length);
 while(discard||done<n) {
  unsigned char t;j=(j+1)%k->length;v=(v+box[j])%k->length;t=box[j];box[j]=box[v];box[v]=t;
  if(discard) discard--;else data[done++]^=box[(box[j]+box[v])%k->length];
 }
 qq_secret_clear(box,sizeof(box));
}
int qq_qmc_apply(const struct qq_qmc_key *k,unsigned char *data,size_t n,uint64_t offset) {
 size_t i=0;
 if(!k||k->length<16||k->length>2048||(!data&&n)||n>65536||offset>268435456||n>268435456-offset) return -1;
 if(k->length<=300) {
  for(i=0;i<n;i++) {
   uint64_t pos=offset+i;unsigned idx,r,v;
   if(pos>32767) pos%=32767;
   idx=(unsigned)((pos*pos+71214)%k->length);r=((idx&7)+4)%8;v=k->key[idx];
   data[i]^=(unsigned char)(r?((v<<r)|(v>>r)):v);
  }
 } else {
  while(i<n&&offset<128) {data[i++]^=k->key[skip(k,offset)];offset++;}
  while(i<n) {size_t count=5120-(size_t)(offset%5120);if(count>n-i) count=n-i;rc4_segment(k,data+i,count,offset);i+=count;offset+=count;}
 }
 return 0;
}
static uint32_t be(const unsigned char *p) {return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static void put(unsigned char *p,uint32_t v) {p[0]=(unsigned char)(v>>24);p[1]=(unsigned char)(v>>16);p[2]=(unsigned char)(v>>8);p[3]=(unsigned char)v;}
static void tea_block(unsigned char *p,const unsigned char *key) {
 uint32_t a=be(p),b=be(p+4),sum=0xe3779b90;unsigned i;
 for(i=0;i<16;i++) {b-=((a<<4)+be(key+8))^(a+sum)^((a>>5)+be(key+12));a-=((b<<4)+be(key))^(b+sum)^((b>>5)+be(key+4));sum-=0x9e3779b9;}
 put(p,a);put(p+4,b);
}
struct tea_reader {const unsigned char *input,*key;size_t bytes,next,index;unsigned char dest[8],previous[8],current[8];};
static int tea_byte(struct tea_reader *r,unsigned char *out) {
 unsigned i;
 if(r->index==8) {
  if(r->next+8>r->bytes) return -1;
  memcpy(r->previous,r->current,8);memcpy(r->current,r->input+r->next,8);
  for(i=0;i<8;i++) r->dest[i]^=r->input[r->next+i];
  tea_block(r->dest,r->key);r->next+=8;r->index=0;
 }
 *out=r->dest[r->index]^r->previous[r->index];r->index++;return 0;
}
static int tea(const unsigned char *data,size_t n,const unsigned char *key,unsigned char *out,size_t cap,size_t *bytes) {
 struct tea_reader r;size_t i,length;unsigned char v;int rc=-1;
 memset(&r,0,sizeof(r));*bytes=0;
 if(n<16||n%8) goto done;
 memcpy(r.dest,data,8);tea_block(r.dest,key);r.index=1+(r.dest[0]&7);
 if(n<10u+(r.dest[0]&7u)) goto done;
 length=n-1-(r.dest[0]&7)-2-7;if(length>cap) goto done;
 r.input=data;r.key=key;r.bytes=n;r.next=8;memcpy(r.current,data,8);
 for(i=0;i<2;i++) if(tea_byte(&r,&v)) goto done;
 for(i=0;i<length;i++) if(tea_byte(&r,out+i)) goto done;
 for(i=0;i<7;i++) if(tea_byte(&r,&v)||v) goto done;
 *bytes=length;rc=0;
done:
 qq_secret_clear(&r,sizeof(r));if(rc) qq_secret_clear(out,cap);return rc;
}
static int b64(const unsigned char *s,size_t n,unsigned char *out,size_t cap,size_t *bytes) {
 size_t i,k=0,digits=0,padding=0;unsigned bits=0,acc=0;
 for(i=0;i<n;i++) {
  unsigned c=s[i],v;
  if(c=='=') {padding++;continue;}
  if(padding) return -1;
  if(c>='A'&&c<='Z') v=c-'A';else if(c>='a'&&c<='z') v=c-'a'+26;
  else if(c>='0'&&c<='9') v=c-'0'+52;else if(c=='+') v=62;else if(c=='/') v=63;else return -1;
  digits++;acc=(acc<<6)|v;bits+=6;
  if(bits>=8) {bits-=8;if(k==cap) return -1;out[k++]=(unsigned char)(acc>>bits);acc&=(1u<<bits)-1;}
 }
 if(!digits||digits%4==1||padding>2||(padding&&(padding!=(4-digits%4)%4||n%4))||acc) return -1;
 *bytes=k;return 0;
}
int qq_qmc_derive(struct qq_qmc_key *out,const char *encoded,size_t n) {
 static const unsigned char simple[]={0x69,0x56,0x46,0x38,0x2b,0x20,0x15,0x0b};
 static const unsigned char v1[]="386ZJY!@#*$%^&)(",v2[]="**#!(#$%&^a1cZ,T",prefix[]="QQMusic EncV2,Key:";
 unsigned char a[4096],b[4096],c[4096],tk[16];size_t an=0,bn=0,cn=0,i;int rc=-1;
 if(!out) return -1;
 qq_qmc_clear(out);
 memset(a,0,sizeof(a));memset(b,0,sizeof(b));memset(c,0,sizeof(c));memset(tk,0,sizeof(tk));
 if(!encoded||!n||n>4096||b64((const unsigned char *)encoded,n,a,sizeof(a),&an)) goto done;
 if(an>=sizeof(prefix)-1&&!memcmp(a,prefix,sizeof(prefix)-1)) {
  if(tea(a+sizeof(prefix)-1,an-sizeof(prefix)+1,v1,b,sizeof(b),&bn)||tea(b,bn,v2,c,sizeof(c),&cn)||b64(c,cn,a,sizeof(a),&an)) goto done;
 }
 if(an<16) goto done;
 for(i=0;i<8;i++) {tk[i*2]=simple[i];tk[i*2+1]=a[i];}
 if(!tea(a+8,an-8,tk,b,sizeof(b),&bn)) {
  if(bn>sizeof(a)-8) goto done;
  memcpy(a+8,b,bn);an=bn+8;
 }
 rc=qq_qmc_init(out,a,an);
done:
 qq_secret_clear(a,sizeof(a));qq_secret_clear(b,sizeof(b));qq_secret_clear(c,sizeof(c));qq_secret_clear(tk,sizeof(tk));
 if(rc) qq_qmc_clear(out);
 return rc;
}
