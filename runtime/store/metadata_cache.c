#define _XOPEN_SOURCE 700
#include "metadata_cache.h"
#include "https_url.h"
#include "../native/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <limits.h>
#include <errno.h>
#include "target_abi.h"
static int stopped(const struct hb_metadata_cache *c){return c->stop&&*c->stop;}
int hb_metadata_cache_key(const char *url,unsigned bytes,const unsigned char digest[32],char key[33]){
 if(!url||!digest||!key||!bytes||bytes>HB_METADATA_CACHE_BYTES)return HB_META_CACHE_INPUT;
 struct hb_https_url parsed;if(hb_https_url_parse(url,&parsed))return HB_META_CACHE_INPUT;
 struct hb_sha256 h;unsigned char hash[32],size[4]={(unsigned char)bytes,(unsigned char)(bytes>>8),(unsigned char)(bytes>>16),(unsigned char)(bytes>>24)};
 hb_sha256_init(&h);hb_sha256_update(&h,(const unsigned char *)"HBMETA1",7);hb_sha256_update(&h,(const unsigned char *)url,(unsigned)strlen(url));hb_sha256_update(&h,digest,32);hb_sha256_update(&h,size,4);hb_sha256_final(&h,hash);
 const char *hex="0123456789abcdef";for(unsigned i=0;i<16;i++){key[i*2]=hex[hash[i]>>4];key[i*2+1]=hex[hash[i]&15];}key[32]=0;return 0;
}
static int parent_same(const struct hb_metadata_cache *c){struct stat s;return !lstat(c->parent,&s)&&S_ISDIR(s.st_mode)&&(unsigned long long)s.st_dev==c->parent_device&&(unsigned long long)s.st_ino==c->parent_inode;}
static int same(const struct hb_metadata_cache *c,const struct stat *s){return S_ISREG(s->st_mode)&&s->st_nlink==1&&s->st_size==(long long)c->actual&&(unsigned long long)s->st_dev==c->device&&(unsigned long long)s->st_ino==c->inode;}
static int read_target(struct hb_metadata_cache *c,unsigned char *data,int compare){
 int fd=open(c->path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return HB_META_CACHE_IO;
 struct stat first,last;int result=HB_META_CACHE_IO;unsigned used=0;unsigned char block[4096],hash[32];struct hb_sha256 h;hb_sha256_init(&h);
 if(fstat(fd,&first)||!same(c,&first))goto done;
 while(used<c->actual){
  if(stopped(c)){result=HB_META_CACHE_CANCELLED;goto done;}
  unsigned amount=c->actual-used;if(amount>sizeof block)amount=sizeof block;
  ssize_t n=read(fd,block,amount);if(n<0&&errno==EINTR)continue;if(n<=0)goto done;
  hb_sha256_update(&h,block,(unsigned)n);if(data)memcpy(data+used,block,(unsigned)n);used+=(unsigned)n;
 }
 unsigned char extra;ssize_t n;do{n=read(fd,&extra,1);}while(n<0&&errno==EINTR&&!stopped(c));if(n)goto done;
 hb_sha256_final(&h,hash);
 if(compare){if(memcmp(hash,c->observed_sha256,32))goto done;}else memcpy(c->observed_sha256,hash,32);
 if(fstat(fd,&last)||!same(c,&last)||lstat(c->path,&last)||!same(c,&last))goto done;
 result=stopped(c)?HB_META_CACHE_CANCELLED:0;
done:
 if(close(fd)&&!result)result=HB_META_CACHE_IO;
 return result;
}
int hb_metadata_cache_inspect(const char *parent,const char *url,unsigned bytes,const unsigned char digest[32],volatile int *stop,unsigned char *data,unsigned capacity,struct hb_metadata_cache *out){
 if(!out)return HB_META_CACHE_INPUT;
 memset(out,0,sizeof *out);out->stop=stop;
 if(!data||capacity<bytes||!parent||strlen(parent)>460||hb_metadata_cache_key(url,bytes,digest,out->key))return HB_META_CACHE_INPUT;
 memset(data,0,bytes);if(stopped(out))return HB_META_CACHE_CANCELLED;
 char canonical[PATH_MAX];struct stat root,s;
 if(!realpath(parent,canonical)||strcmp(parent,canonical)||lstat(parent,&root)||!S_ISDIR(root.st_mode))return HB_META_CACHE_IO;
 strcpy(out->parent,parent);out->parent_device=(unsigned long long)root.st_dev;out->parent_inode=(unsigned long long)root.st_ino;out->expected=bytes;memcpy(out->expected_sha256,digest,32);
 int n=snprintf(out->path,sizeof out->path,"%s%s.fetch-%s",parent,strlen(parent)==1?"":"/",out->key);if(n<0||n>=(int)sizeof out->path)return HB_META_CACHE_INPUT;
 if(lstat(out->path,&s))return errno==ENOENT?HB_META_CACHE_ABSENT:HB_META_CACHE_IO;
 if(!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size<0||(unsigned long long)s.st_size>bytes||(unsigned long long)s.st_dev!=out->parent_device)return HB_META_CACHE_INPUT;
 out->actual=(unsigned)s.st_size;out->device=(unsigned long long)s.st_dev;out->inode=(unsigned long long)s.st_ino;
 int result=read_target(out,data,0);if(!result&&!parent_same(out))result=HB_META_CACHE_IO;
 if(!result&&stopped(out))result=HB_META_CACHE_CANCELLED;
 if(result){memset(data,0,bytes);return result;}
 out->complete=out->actual==bytes&&!memcmp(out->expected_sha256,out->observed_sha256,32);out->valid=1;
 if(out->complete)return 0;
 memset(data,0,bytes);return HB_META_CACHE_PREVIOUS;
}
int hb_metadata_cache_discard(struct hb_metadata_cache *c){
 if(!c||!c->valid)return HB_META_CACHE_INPUT;
 if(stopped(c))return HB_META_CACHE_CANCELLED;
 if(!parent_same(c))return HB_META_CACHE_IO;
 struct stat s;
 if(c->removed){if(!lstat(c->path,&s)||errno!=ENOENT)return HB_META_CACHE_IO;}
 else {
  int result=read_target(c,0,1);if(result)return result;
  if(stopped(c))return HB_META_CACHE_CANCELLED;
  if(unlink(c->path)){if(lstat(c->path,&s)&&errno==ENOENT)c->removed=1;return HB_META_CACHE_IO;}
  c->removed=1;
 }
 int fd=open(c->parent,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return HB_META_CACHE_IO;
 int result=fstat(fd,&s)||!S_ISDIR(s.st_mode)||(unsigned long long)s.st_dev!=c->parent_device||(unsigned long long)s.st_ino!=c->parent_inode?HB_META_CACHE_IO:0;
 if(!result&&fsync(fd))result=HB_META_CACHE_IO;
 if(close(fd)&&!result)result=HB_META_CACHE_IO;
 if(stopped(c))return HB_META_CACHE_CANCELLED;
 if(!result)c->valid=0;
 return result;
}
