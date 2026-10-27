#define _XOPEN_SOURCE 700
#include "download_record.h"
#include "../native/sha256.h"
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <limits.h>
#include <errno.h>
#include "target_abi.h"
static int stopped(const struct hb_download_record *r){return r->stop&&*r->stop;}
static int review(struct hb_download_record *r,int error){r->state=HB_RECORD_REVIEW;return error;}
static int parent_same(const struct hb_download_record *r){struct stat s;return !lstat(r->parent,&s)&&S_ISDIR(s.st_mode)&&(unsigned long long)s.st_dev==r->parent_device&&(unsigned long long)s.st_ino==r->parent_inode;}
static int file_same(const struct hb_download_record *r,const struct stat *s){return r->identity_known&&S_ISREG(s->st_mode)&&s->st_nlink==1&&(unsigned long long)s->st_dev==r->device&&(unsigned long long)s->st_ino==r->inode&&s->st_size>=0&&(unsigned long long)s->st_size<=r->bytes;}
static int sync_parent(struct hb_download_record *r){
 if(stopped(r))return HB_RECORD_CANCELLED;
 if(!parent_same(r))return HB_RECORD_IO;
 int fd=open(r->parent,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return HB_RECORD_IO;
 int result=fsync(fd);if(close(fd))result=-1;return stopped(r)?HB_RECORD_CANCELLED:result?HB_RECORD_IO:0;
}
void hb_download_record_init(struct hb_download_record *r){if(r){memset(r,0,sizeof *r);r->fd=-1;}}
static int prepare(struct hb_download_record *r,const char *parent,const struct hb_package_download_plan *p,volatile int *stop){
 if(!r||r->state!=HB_RECORD_EMPTY||r->owns||r->fd>=0||!parent||strlen(parent)>400||!p||!p->valid)return HB_RECORD_INPUT;
 r->stop=stop;if(stopped(r))return HB_RECORD_CANCELLED;
 unsigned char identity[32];if(hb_bundle_identity(&p->bundle,identity)||memcmp(identity,p->identity,32))return HB_RECORD_INPUT;
 char canonical[PATH_MAX];struct stat s;
 if(!realpath(parent,canonical)||strcmp(parent,canonical)||lstat(parent,&s)||!S_ISDIR(s.st_mode))return HB_RECORD_IO;
 strcpy(r->parent,parent);r->parent_device=(unsigned long long)s.st_dev;r->parent_inode=(unsigned long long)s.st_ino;
 int n=snprintf(r->path,sizeof r->path,"%s%s.download-%s.intent",parent,strlen(parent)==1?"":"/",p->bundle.package.id);if(n<0||n>=(int)sizeof r->path)return HB_RECORD_INPUT;strcpy(r->final_path,r->path);return 0;
}
static int close_file(struct hb_download_record *r,int result){if(r->fd>=0){if(close(r->fd)&&!result)result=HB_RECORD_IO;r->fd=-1;}return result;}
static int stage_absent(const struct hb_download_record *r,const struct hb_package_download_plan *p){
 char stage[512];struct stat existing;int n=snprintf(stage,sizeof stage,"%s%s.bundle-%s",r->parent,strlen(r->parent)==1?"":"/",p->bundle.package.id);
 if(n<0||n>=(int)sizeof stage)return HB_RECORD_INPUT;
 if(!lstat(stage,&existing))return HB_RECORD_EXISTS;
 return errno==ENOENT?0:HB_RECORD_IO;
}
static int temporary_path(struct hb_download_record *r,const struct hb_package_download_plan *p){
 struct hb_sha256 h;unsigned char digest[32];char hex[65];static const char digits[]="0123456789abcdef";
 hb_sha256_init(&h);hb_sha256_update(&h,r->encoded,r->bytes);hb_sha256_final(&h,digest);
 for(unsigned i=0;i<32;i++){hex[i*2]=digits[digest[i]>>4];hex[i*2+1]=digits[digest[i]&15];}hex[64]=0;
 int n=snprintf(r->path,sizeof r->path,"%s%s.save-%s-%s",r->parent,strlen(r->parent)==1?"":"/",p->bundle.package.id,hex);return n<0||n>=(int)sizeof r->path?HB_RECORD_INPUT:0;
}
int hb_download_record_save(struct hb_download_record *r,const char *parent,const struct hb_package_download_plan *p,unsigned long long reserve,volatile int *stop){
 int result=prepare(r,parent,p,stop);if(result)return result;
 result=stage_absent(r,p);if(result)return result;
 struct stat existing;if(!lstat(r->final_path,&existing))return HB_RECORD_EXISTS;if(errno!=ENOENT)return HB_RECORD_IO;
 if(hb_download_intent_create(p,&r->intent)||hb_download_intent_encode(&r->intent,r->encoded,sizeof r->encoded,&r->bytes))return HB_RECORD_INPUT;
 result=temporary_path(r,p);if(result)return result;
 if(!lstat(r->path,&existing))return HB_RECORD_STAGED;
 if(errno!=ENOENT)return HB_RECORD_IO;
 struct statvfs space;if(statvfs(parent,&space))return HB_RECORD_IO;unsigned long long unit=space.f_frsize;
 if(unit<512||unit>1048576||(unit&(unit-1))||space.f_bavail>~0ULL/unit)return HB_RECORD_IO;
 unsigned long long needed=(((unsigned long long)r->bytes+unit-1)/unit+2)*unit;if(needed+reserve<needed||space.f_bavail*unit<needed+reserve)return HB_RECORD_SPACE;
 if(stopped(r))return HB_RECORD_CANCELLED;
 r->fd=open(r->path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(r->fd<0)return errno==EEXIST?HB_RECORD_STAGED:HB_RECORD_IO;
 r->owns=r->provisional=1;struct stat s;
 if(fstat(r->fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||(unsigned long long)s.st_dev!=r->parent_device)return review(r,close_file(r,HB_RECORD_IO));
 r->device=(unsigned long long)s.st_dev;r->inode=(unsigned long long)s.st_ino;r->identity_known=1;unsigned used=0;
 while(used<r->bytes){if(stopped(r)){result=HB_RECORD_CANCELLED;break;}ssize_t n=write(r->fd,r->encoded+used,r->bytes-used);if(n<0&&errno==EINTR)continue;if(n<=0){result=HB_RECORD_IO;break;}used+=(unsigned)n;}
 if(!result&&stopped(r))result=HB_RECORD_CANCELLED;
 if(!result&&fsync(r->fd))result=HB_RECORD_IO;
 result=close_file(r,result);if(!result&&(lstat(r->path,&s)||!file_same(r,&s)||s.st_size!=(long long)r->bytes))result=HB_RECORD_IO;
 if(!result){
  if(!lstat(r->final_path,&s)||errno!=ENOENT)result=HB_RECORD_EXISTS;
  else if(stopped(r))result=HB_RECORD_CANCELLED;
  else if(rename(r->path,r->final_path)){
   struct stat final,old;result=HB_RECORD_IO;
   if(!lstat(r->final_path,&final)&&file_same(r,&final)&&final.st_size==(long long)r->bytes&&lstat(r->path,&old)&&errno==ENOENT){strcpy(r->path,r->final_path);r->provisional=0;}
  }
  else {strcpy(r->path,r->final_path);r->provisional=0;}
 }
 if(!result&&(lstat(r->path,&s)||!file_same(r,&s)||s.st_size!=(long long)r->bytes))result=HB_RECORD_IO;
 if(!result)result=sync_parent(r);
 if(result)return review(r,result);
 r->state=HB_RECORD_READY;return 0;
}
int hb_download_record_load(struct hb_download_record *r,const char *parent,const struct hb_package_download_plan *p,volatile int *stop){
 int result=prepare(r,parent,p,stop);if(result)return result;r->intent.valid=0;
 r->fd=open(r->path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(r->fd<0)return errno==ENOENT?HB_RECORD_ABSENT:review(r,HB_RECORD_IO);
 struct stat first,last;
 if(fstat(r->fd,&first)||!S_ISREG(first.st_mode)||first.st_nlink!=1||first.st_size<=0||(unsigned long long)first.st_size>sizeof r->encoded||(unsigned long long)first.st_dev!=r->parent_device)return review(r,close_file(r,HB_RECORD_IO));
 r->bytes=(unsigned)first.st_size;unsigned used=0;
 while(used<r->bytes){if(stopped(r)){result=HB_RECORD_CANCELLED;break;}ssize_t n=read(r->fd,r->encoded+used,r->bytes-used);if(n<0&&errno==EINTR)continue;if(n<=0){result=HB_RECORD_IO;break;}used+=(unsigned)n;}
 unsigned char extra;ssize_t tail=0;if(!result){do{tail=read(r->fd,&extra,1);}while(tail<0&&errno==EINTR&&!stopped(r));if(tail)result=HB_RECORD_IO;}
 if(!result&&(fstat(r->fd,&last)||last.st_dev!=first.st_dev||last.st_ino!=first.st_ino||last.st_size!=first.st_size))result=HB_RECORD_IO;
 result=close_file(r,result);
 if(!result&&(hb_download_intent_decode(r->encoded,r->bytes,p->bundle.package.id,&r->intent)||hb_download_intent_matches(&r->intent,p)))result=HB_RECORD_INPUT;
 if(!result&&(!parent_same(r)||lstat(r->path,&last)||!S_ISREG(last.st_mode)||last.st_nlink!=1||last.st_dev!=first.st_dev||last.st_ino!=first.st_ino||last.st_size!=first.st_size))result=HB_RECORD_IO;
 if(stopped(r))result=HB_RECORD_CANCELLED;
 if(result){r->intent.valid=0;return review(r,result);}
 r->device=(unsigned long long)first.st_dev;r->inode=(unsigned long long)first.st_ino;r->identity_known=r->owns=1;r->provisional=0;r->state=HB_RECORD_READY;return 0;
}
static int owned_prefix(struct hb_download_record *r){
 int fd=open(r->path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return HB_RECORD_IO;
 struct stat first,last;unsigned used=0;int result=HB_RECORD_IO;unsigned char data[4096];
 if(fstat(fd,&first)||!file_same(r,&first)||(!r->provisional&&first.st_size!=(long long)r->bytes))goto done;
 for(;;){if(stopped(r)){result=HB_RECORD_CANCELLED;goto done;}ssize_t n=read(fd,data,sizeof data);if(n<0&&errno==EINTR)continue;if(n<0)goto done;if(!n)break;if((unsigned)n>r->bytes-used||memcmp(data,r->encoded+used,(unsigned)n))goto done;used+=(unsigned)n;}
 if(used!=(unsigned)first.st_size||fstat(fd,&last)||!file_same(r,&last)||last.st_size!=first.st_size||lstat(r->path,&last)||!file_same(r,&last)||last.st_size!=first.st_size)goto done;
 result=0;
done:
 if(close(fd)&&!result)result=HB_RECORD_IO;
 return result;
}
int hb_download_record_review_temporary(struct hb_download_record *r,const char *parent,const struct hb_package_download_plan *p,volatile int *stop){
 int result=prepare(r,parent,p,stop);if(result)return result;
 result=stage_absent(r,p);if(result)return result;
 struct stat s;if(!lstat(r->final_path,&s))return HB_RECORD_EXISTS;if(errno!=ENOENT)return HB_RECORD_IO;
 if(hb_download_intent_create(p,&r->intent)||hb_download_intent_encode(&r->intent,r->encoded,sizeof r->encoded,&r->bytes)||temporary_path(r,p))return HB_RECORD_INPUT;
 int fd=open(r->path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return errno==ENOENT?HB_RECORD_ABSENT:review(r,HB_RECORD_IO);
 result=fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size<0||(unsigned long long)s.st_size>r->bytes||(unsigned long long)s.st_dev!=r->parent_device?HB_RECORD_INPUT:0;
 if(close(fd)&&!result)result=HB_RECORD_IO;
 if(result)return review(r,result);
 r->device=(unsigned long long)s.st_dev;r->inode=(unsigned long long)s.st_ino;r->identity_known=1;r->provisional=1;
 result=owned_prefix(r);if(!result&&!parent_same(r))result=HB_RECORD_IO;if(!result)result=stage_absent(r,p);
 if(stopped(r))result=HB_RECORD_CANCELLED;
 if(result){r->identity_known=0;r->intent.valid=0;return review(r,result);}
 r->owns=1;r->state=HB_RECORD_REVIEW;return 0;
}
int hb_download_record_check(struct hb_download_record *r){
 if(!r||!r->owns||!r->identity_known||r->provisional||r->removed||r->fd>=0||(r->state!=HB_RECORD_READY&&r->state!=HB_RECORD_REVIEW))return HB_RECORD_INPUT;
 if(stopped(r))return HB_RECORD_CANCELLED;
 if(!parent_same(r))return review(r,HB_RECORD_IO);
 int result=owned_prefix(r);if(result)return review(r,result);
 r->state=HB_RECORD_READY;return 0;
}
int hb_download_record_discard(struct hb_download_record *r){
 if(!r||!r->owns||!r->identity_known||r->fd>=0||(r->state!=HB_RECORD_READY&&r->state!=HB_RECORD_REVIEW))return HB_RECORD_INPUT;
 if(stopped(r))return HB_RECORD_CANCELLED;
 if(!parent_same(r))return review(r,HB_RECORD_IO);
 int result;struct stat s;
 if(r->removed){if(!lstat(r->path,&s)||errno!=ENOENT)return review(r,HB_RECORD_IO);}
 else {
  result=owned_prefix(r);if(result)return review(r,result);
  if(stopped(r))return HB_RECORD_CANCELLED;
  if(unlink(r->path))return review(r,HB_RECORD_IO);
  r->removed=1;
 }
 result=sync_parent(r);if(result)return review(r,result);hb_download_record_init(r);return 0;
}
