#define _XOPEN_SOURCE 700
#include "repository.h"
#include "https_url.h"
#include "../native/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#include "target_abi.h"
static int digest(const char *s,unsigned char out[32]){if(strlen(s)!=64)return -1;for(unsigned i=0;i<32;i++){unsigned value=0;for(unsigned k=0;k<2;k++){char c=s[i*2+k];unsigned n;if(c>='0'&&c<='9')n=(unsigned)(c-'0');else if(c>='a'&&c<='f')n=(unsigned)(c-'a'+10);else return -1;value=value*16+n;}out[i]=(unsigned char)value;}return 0;}
static int number(const char *s,unsigned *out){unsigned n=0;if(!*s||(*s=='0'&&s[1]))return -1;for(;*s;s++){if(*s<'0'||*s>'9'||n>(32768u-(unsigned)(*s-'0'))/10)return -1;n=n*10+(unsigned)(*s-'0');}if(!n||n>32768)return -1;*out=n;return 0;}
int hb_repository_parse(const unsigned char *data,unsigned bytes,struct hb_repository_spec *out){
 if(!out)return HB_REPO_INPUT;
 out->valid=0;
 if(!data||bytes<8||bytes>HB_REPOSITORY_CONFIG_BYTES||memcmp(data,"HBREPO1\n",8)||data[bytes-1]!='\n')return HB_REPO_INPUT;
 unsigned pos=8,seen=0;
 while(pos<bytes){char line[2560];unsigned used=0;
  while(pos<bytes&&data[pos]!='\n'){unsigned char c=data[pos++];if(c<32||c>126||used+1>=sizeof line)return HB_REPO_INPUT;line[used++]=(char)c;}
  if(pos==bytes||!used)return HB_REPO_INPUT;
  pos++;line[used]=0;char *value=strchr(line,'=');if(!value)return HB_REPO_INPUT;*value++=0;unsigned flag;
  if(!strcmp(line,"catalog_url")){
   flag=1;unsigned n=(unsigned)strlen(value);struct hb_https_url url;if(!n||n>=sizeof out->catalog_url||strchr(value,'#')||hb_https_url_parse(value,&url))return HB_REPO_INPUT;strcpy(out->catalog_url,value);
  }else if(!strcmp(line,"catalog_bytes")){flag=2;if(number(value,&out->catalog_bytes))return HB_REPO_INPUT;}
  else if(!strcmp(line,"catalog_sha256")){flag=4;if(digest(value,out->catalog_sha256))return HB_REPO_INPUT;}
  else if(!strcmp(line,"ca_sha256")){flag=8;if(digest(value,out->ca_sha256))return HB_REPO_INPUT;}
  else return HB_REPO_INPUT;
  if(seen&flag)return HB_REPO_INPUT;
  seen|=flag;
 }
 if(seen!=15)return HB_REPO_INPUT;
 out->valid=1;return 0;
}
static int stopped(volatile int *stop){return stop&&*stop;}
static int same(const struct stat *a,const struct stat *b){return a->st_dev==b->st_dev&&a->st_ino==b->st_ino&&a->st_size==b->st_size&&S_ISREG(b->st_mode)&&b->st_nlink==1;}
static int read_file(const char *path,unsigned limit,unsigned long long device,volatile int *stop,struct hb_repository *r){
 if(stopped(stop))return HB_REPO_CANCELLED;
 int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return errno==ENOENT?HB_REPO_MISSING:HB_REPO_IO;
 struct stat initial,final;int result=HB_REPO_IO;unsigned used=0;
 if(fstat(fd,&initial)||!S_ISREG(initial.st_mode)||initial.st_nlink!=1||initial.st_size<=0||(unsigned long long)initial.st_size>limit||(unsigned long long)initial.st_dev!=device)goto done;
 while(used<(unsigned)initial.st_size){if(stopped(stop)){result=HB_REPO_CANCELLED;goto done;}ssize_t n=read(fd,r->raw+used,(unsigned)initial.st_size-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto done;used+=(unsigned)n;}
 unsigned char extra;ssize_t n;do{n=read(fd,&extra,1);}while(n<0&&errno==EINTR&&!stopped(stop));if(n||fstat(fd,&final)||!same(&initial,&final)||lstat(path,&final)||!same(&initial,&final))goto done;
 result=stopped(stop)?HB_REPO_CANCELLED:0;
done:
 if(close(fd)&&!result)result=HB_REPO_IO;
 if(!result)r->raw_bytes=used;
 return result;
}
static void append_dn(void *context,const void *data,size_t bytes){struct hb_repository *r=context;if(bytes>sizeof r->dn-r->dn_bytes){r->dn_overflow=1;return;}memcpy(r->dn+r->dn_bytes,data,bytes);r->dn_bytes+=(unsigned)bytes;}
struct dn_target {unsigned char *data;unsigned *used;int *overflow;};
static void append_extra_dn(void *context,const void *data,size_t bytes){struct dn_target *d=context;if(bytes>1024u-*d->used){*d->overflow=1;return;}memcpy(d->data+*d->used,data,bytes);*d->used+=(unsigned)bytes;}
static int der_complete(const unsigned char *p,unsigned bytes){
 if(bytes<2||p[0]!=0x30)return 0;
 unsigned length=p[1],header=2;
 if(length&128){unsigned count=length&127;if(!count||count>3||bytes<2+count||!p[2])return 0;length=0;for(unsigned i=0;i<count;i++)length=(length<<8)|p[2+i];if(length<128)return 0;header+=count;}
 return length==bytes-header;
}
int hb_repository_load(const char *directory,volatile int *stop,struct hb_repository *r){
 if(!r)return HB_REPO_INPUT;
 memset(r,0,sizeof *r);
 if(!directory||strlen(directory)>400)return HB_REPO_INPUT;
 char resolved[PATH_MAX],path[512];struct stat root,last;
 if(!realpath(directory,resolved))return errno==ENOENT?HB_REPO_MISSING:HB_REPO_IO;
 if(strcmp(directory,resolved)||lstat(directory,&root)||!S_ISDIR(root.st_mode))return HB_REPO_IO;
 unsigned n=(unsigned)strlen(directory);memcpy(path,directory,n);if(n>1)path[n++]='/';memcpy(path+n,"repository.conf",16);
 int result=read_file(path,HB_REPOSITORY_CONFIG_BYTES,(unsigned long long)root.st_dev,stop,r);if(result)return result;
 result=hb_repository_parse(r->raw,r->raw_bytes,&r->spec);if(result)return result;
 memcpy(path+n,"ca.der",7);result=read_file(path,sizeof r->raw,(unsigned long long)root.st_dev,stop,r);if(result)return result;
 struct hb_sha256 hash;unsigned char actual[32];hb_sha256_init(&hash);hb_sha256_update(&hash,r->raw,r->raw_bytes);hb_sha256_final(&hash,actual);if(memcmp(actual,r->spec.ca_sha256,32))return HB_REPO_HASH;
 unsigned offset=0;
 while(offset<r->raw_bytes){
  unsigned available=r->raw_bytes-offset,n=0,header=2;const unsigned char *der=r->raw+offset;
  if(r->anchor_count==8||available<2||der[0]!=0x30)return HB_REPO_CERT;
  if(!(der[1]&128))n=der[1];else{unsigned count=der[1]&127;if(!count||count>3||available<2+count)return HB_REPO_CERT;header+=count;for(unsigned i=0;i<count;i++)n=(n<<8)|der[2+i];}
  if(n>available-header||!der_complete(der,n+header))return HB_REPO_CERT;
  unsigned index=r->anchor_count; br_x509_decoder_context *decoder;struct dn_target target;
  if(!index){decoder=&r->decoder;br_x509_decoder_init(decoder,append_dn,r);}
  else{decoder=&r->extra_ca[index-1].decoder;target.data=r->extra_ca[index-1].dn;target.used=&r->extra_ca[index-1].bytes;target.overflow=&r->extra_ca[index-1].overflow;br_x509_decoder_init(decoder,append_extra_dn,&target);}
  br_x509_decoder_push(decoder,der,n+header);br_x509_pkey *key=br_x509_decoder_get_pkey(decoder);
  unsigned dn_bytes=index?r->extra_ca[index-1].bytes:r->dn_bytes;int overflow=index?r->extra_ca[index-1].overflow:r->dn_overflow;
  if(!key||br_x509_decoder_last_error(decoder)||!br_x509_decoder_isCA(decoder)||!dn_bytes||overflow||(key->key_type!=BR_KEYTYPE_RSA&&key->key_type!=BR_KEYTYPE_EC))return HB_REPO_CERT;
  r->anchors[index].dn.data=index?r->extra_ca[index-1].dn:r->dn;r->anchors[index].dn.len=dn_bytes;r->anchors[index].flags=BR_X509_TA_CA;r->anchors[index].pkey=*key;
  r->anchor_count++;offset+=n+header;
 }
 if(!r->anchor_count)return HB_REPO_CERT;
 if(lstat(directory,&last)||!S_ISDIR(last.st_mode)||last.st_dev!=root.st_dev||last.st_ino!=root.st_ino)return HB_REPO_IO;
 if(stopped(stop))return HB_REPO_CANCELLED;
 r->anchor=r->anchors[0];r->valid=1;return 0;
}
