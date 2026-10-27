#include "../../runtime/apps/qqmusic/qqmusic_qmc.h"
#include <assert.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
static struct qq_qmc_key key;
static unsigned char encoded[4096],raw[2048],data[65536],expected[65536],original[65536];
static void get(int fd,void *out,size_t n) {
 unsigned char *p=out;size_t used=0;while(used<n) {ssize_t count=read(fd,p+used,n-used);assert(count>0&&(size_t)count<=n-used);used+=(size_t)count;}
}
static uint32_t word(int fd) {unsigned char b[4];get(fd,b,4);return b[0]|(uint32_t)b[1]<<8|(uint32_t)b[2]<<16|(uint32_t)b[3]<<24;}
int main(int argc,char **argv) {
 int fd,emit;uint32_t cases,c;unsigned i;assert(argc==2||argc==3);emit=argc==3;assert(!emit||!strcmp(argv[2],"--emit"));fd=open(argv[1],O_RDONLY);assert(fd>=0);cases=word(fd);assert(!emit||cases==1);
 for(c=0;c<cases;c++) {
  unsigned mode=word(fd),encoded_bytes=word(fd),raw_bytes=word(fd),bytes=word(fd);uint64_t offset=word(fd);offset|=(uint64_t)word(fd)<<32;
  assert(encoded_bytes<=sizeof(encoded)&&raw_bytes<=sizeof(raw)&&bytes<=sizeof(data));
  get(fd,encoded,encoded_bytes);get(fd,raw,raw_bytes);get(fd,data,bytes);get(fd,expected,bytes);memcpy(original,data,bytes);
  if(mode==2) {
   assert(qq_qmc_derive(&key,(const char *)encoded,encoded_bytes)<0);
   for(i=0;i<sizeof(key);i++) assert(((unsigned char *)&key)[i]==0);
   continue;
  }
  if(mode==0) assert(qq_qmc_init(&key,encoded,encoded_bytes)==0);
  else assert(qq_qmc_derive(&key,(const char *)encoded,encoded_bytes)==0);
  assert(key.length==raw_bytes&&!memcmp(key.key,raw,raw_bytes));
  assert(qq_qmc_apply(&key,data,bytes,offset)==0&&!memcmp(data,expected,bytes));
  if(emit) assert(write(1,data,bytes)==(ssize_t)bytes);
  assert(qq_qmc_apply(&key,data,bytes,offset)==0&&!memcmp(data,original,bytes));
  if(bytes>213) {assert(qq_qmc_apply(&key,data,213,offset)==0);assert(qq_qmc_apply(&key,data+213,bytes-213,offset+213)==0);assert(!memcmp(data,expected,bytes));}
  qq_qmc_clear(&key);for(i=0;i<sizeof(key);i++) assert(((unsigned char *)&key)[i]==0);
 }
 {unsigned char test_key[16]={0};assert(qq_qmc_init(&key,test_key,sizeof(test_key))==0);
 assert(qq_qmc_apply(&key,data,65537,0)<0&&qq_qmc_apply(&key,data,1,UINT64_MAX)<0);qq_qmc_clear(&key);}
 {unsigned char tail[16]={0};uint64_t audio;int footer;
 assert(qq_qmc_payload_length(100,tail,&audio,&footer)==0&&audio==100&&!footer);
 memcpy(tail+8,"musicex\0",8);tail[0]=32;
 assert(qq_qmc_payload_length(100,tail,&audio,&footer)==0&&audio==68&&footer);
 tail[0]=100;assert(qq_qmc_payload_length(100,tail,&audio,&footer)<0&&audio==0&&!footer);
 tail[0]=15;assert(qq_qmc_payload_length(100,tail,&audio,&footer)<0);}
 assert(close(fd)==0);return 0;
}
