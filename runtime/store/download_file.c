#define _XOPEN_SOURCE 700
#include "download_file.h"
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <limits.h>
#include <stdlib.h>
#include "target_abi.h"
static int retained(struct hb_download_file *f){f->state=HB_FETCH_REVIEW;return HB_FETCH_RETAINED;}
static int same(struct hb_download_file *f){
 struct stat s;return f->identity_known&&!lstat(f->path,&s)&&S_ISREG(s.st_mode)&&s.st_nlink==1&&
  (unsigned long long)s.st_dev==f->device&&(unsigned long long)s.st_ino==f->inode;
}
static int sync_folder(struct hb_download_file *f){
 int fd=open(f->folder,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 int result=fsync(fd);if(close(fd))result=-1;return result;
}
static int sink(void *context,const unsigned char *data,unsigned bytes){
 struct hb_download_file *f=context;
 if(f->state!=HB_FETCH_OPEN||f->fd<0)return -1;
 for(;;){
  if(f->body.stop&&*f->body.stop)return -1;
  ssize_t n=write(f->fd,data,bytes);if(n<0&&errno==EINTR)continue;return (int)n;
 }
}
void hb_download_file_init(struct hb_download_file *f){if(f){f->fd=-1;f->owns=f->identity_known=0;f->state=HB_FETCH_EMPTY;}}
int hb_download_file_begin(struct hb_download_file *f,const char *folder,const char *key,
 unsigned bytes,const unsigned char *digest,unsigned long long reserve,volatile int *stop){
 if(!f||f->state!=HB_FETCH_EMPTY||!folder||!key)return HB_FETCH_IO;
 unsigned length=0;for(;length<=32&&key[length];length++)if(!((key[length]>='a'&&key[length]<='z')||
  (key[length]>='0'&&key[length]<='9')||(length&&key[length]=='-')))return HB_FETCH_IO;
 if(!length||length>32||strlen(folder)>460)return HB_FETCH_IO;
 int result=hb_download_stream_init(&f->body,bytes,digest,f,sink,stop);if(result)return result;
 if(stop&&*stop)return HB_DOWNLOAD_CANCELLED;
 char resolved[PATH_MAX];struct stat parent;struct statvfs space;
 if(!realpath(folder,resolved)||strcmp(folder,resolved)||lstat(folder,&parent)||!S_ISDIR(parent.st_mode)||statvfs(folder,&space))return HB_FETCH_IO;
 unsigned long long unit=space.f_frsize;
 if(unit<512||unit>1048576||(unit&(unit-1))||space.f_bavail>~0ULL/unit)return HB_FETCH_IO;
 unsigned long long needed=(((unsigned long long)bytes+unit-1)/unit+2)*unit;
 if(needed+reserve<needed||space.f_bavail*unit<needed+reserve)return HB_FETCH_SPACE;
 strcpy(f->folder,folder);unsigned p=0;while(folder[p]){f->path[p]=folder[p];p++;}
 if(p>1)f->path[p++]='/';
 const char *prefix=".fetch-";for(unsigned i=0;prefix[i];i++)f->path[p++]=prefix[i];
 for(unsigned i=0;i<=length;i++)f->path[p++]=key[i];
 f->identity_known=0;
 f->fd=open(f->path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
 if(f->fd<0)return errno==EEXIST?HB_FETCH_EXISTS:HB_FETCH_IO;
 f->owns=1;struct stat file;
 if(fstat(f->fd,&file)||!S_ISREG(file.st_mode)||file.st_nlink!=1||file.st_dev!=parent.st_dev){close(f->fd);f->fd=-1;return retained(f);}
 f->device=(unsigned long long)file.st_dev;f->inode=(unsigned long long)file.st_ino;f->identity_known=1;f->state=HB_FETCH_OPEN;return 0;
}
int hb_download_file_finish(struct hb_download_file *f){
 if(!f||f->state!=HB_FETCH_OPEN||f->fd<0)return HB_FETCH_IO;
 if(f->body.state!=HB_DOWNLOAD_VERIFIED){int result=hb_download_stream_finish(&f->body);if(result)return result;}
 if(f->body.stop&&*f->body.stop)return HB_DOWNLOAD_CANCELLED;
 int result=fsync(f->fd);if(close(f->fd))result=-1;f->fd=-1;
 if(result||!same(f)||sync_folder(f))return retained(f);
 f->state=HB_FETCH_READY;return 0;
}
int hb_download_file_discard(struct hb_download_file *f){
 if(!f)return HB_FETCH_IO;
 if(f->state==HB_FETCH_EMPTY&&!f->owns)return 0;
 if(f->state==HB_FETCH_REVIEW)return HB_FETCH_RETAINED;
 if(f->fd>=0){int result=close(f->fd);f->fd=-1;if(result)return retained(f);}
 if(f->body.stop&&*f->body.stop)return HB_DOWNLOAD_CANCELLED;
 if(!f->owns||!same(f)||unlink(f->path)||sync_folder(f))return retained(f);
 f->owns=f->identity_known=0;f->state=HB_FETCH_EMPTY;return 0;
}
int hb_download_file_recheck(struct hb_download_file *f){
 if(!f||f->state!=HB_FETCH_REVIEW||!f->owns||!f->identity_known||f->fd>=0)return HB_FETCH_RETAINED;
 if(f->body.stop&&*f->body.stop)return HB_DOWNLOAD_CANCELLED;
 if(!same(f)||f->body.expected>134217728u)return HB_FETCH_RETAINED;
 int fd=open(f->path,O_RDONLY|O_NOFOLLOW);if(fd<0)return HB_FETCH_RETAINED;
 struct stat info;int result=HB_FETCH_RETAINED;unsigned total=0;
 if(fstat(fd,&info)||!S_ISREG(info.st_mode)||info.st_nlink!=1||
    (unsigned long long)info.st_dev!=f->device||(unsigned long long)info.st_ino!=f->inode||
    info.st_size!=(long long)f->body.expected)goto done;
 struct hb_sha256 hash;hb_sha256_init(&hash);unsigned char buffer[4096],digest[32];
 for(;;){
  if(f->body.stop&&*f->body.stop){result=HB_DOWNLOAD_CANCELLED;goto done;}
  ssize_t n=read(fd,buffer,sizeof buffer);if(n<0&&errno==EINTR)continue;
  if(n<0)goto done;
  if(!n)break;
  if((unsigned)n>f->body.expected-total)goto done;
  hb_sha256_update(&hash,buffer,(unsigned)n);total+=(unsigned)n;
 }
 if(total!=f->body.expected)goto done;
 hb_sha256_final(&hash,digest);unsigned difference=0;for(unsigned i=0;i<32;i++)difference|=digest[i]^f->body.digest[i];
 if(difference||!same(f))goto done;
 if(f->body.stop&&*f->body.stop){result=HB_DOWNLOAD_CANCELLED;goto done;}
 if(fsync(fd))goto done;
 result=0;
done:
 if(close(fd))result=HB_FETCH_RETAINED;
 if(!result&&(f->body.stop&&*f->body.stop))result=HB_DOWNLOAD_CANCELLED;
 if(!result&&(!same(f)||sync_folder(f)))result=HB_FETCH_RETAINED;
 if(!result&&(f->body.stop&&*f->body.stop))result=HB_DOWNLOAD_CANCELLED;
 if(!result){f->state=HB_FETCH_READY;f->body.state=HB_DOWNLOAD_VERIFIED;f->body.error=0;}
 return result;
}
