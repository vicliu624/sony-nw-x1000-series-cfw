#define _XOPEN_SOURCE 700
#include "stage_posix.h"
#include "../native/sha256.h"
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "target_abi.h"
static int stopped(volatile int *stop){return stop&&*stop;}
static int join(char *out,const char *a,const char *b) {
 int n=snprintf(out,512,"%s/%s",a,b);return n<0||n>=512?-1:0;
}
static int sync_dir(const char *path) {
 int fd=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 int result=fsync(fd);if(close(fd))result=-1;return result;
}
static int parents(const char *stage,const char *relative,dev_t device) {
 char partial[161],path[512];unsigned n=(unsigned)strlen(relative);struct stat s;
 if(n>=sizeof partial)return -1;
 memcpy(partial,relative,n+1);
 for(unsigned i=0;i<n;i++)if(partial[i]=='/') {
  partial[i]=0;
  if(join(path,stage,partial))return -1;
  if(mkdir(path,0700)&&errno!=EEXIST)return -1;
  if(lstat(path,&s)||!S_ISDIR(s.st_mode)||s.st_dev!=device)return -1;
  partial[i]='/';
 }
 return 0;
}
static int copy_file(const char *source,const char *stage,const char *relative,
                     unsigned bytes,const unsigned char expected[32],dev_t device,
                     volatile int *stop) {
 char input[512],output[512];struct stat s;struct hb_sha256 hash;
 unsigned total=0;unsigned char buffer[4096],digest[32];int result=HB_STAGE_IO;
 if(join(input,source,relative)||join(output,stage,relative)||parents(stage,relative,device))return HB_STAGE_IO;
 int in=open(input,O_RDONLY|O_NOFOLLOW);if(in<0)return HB_STAGE_IO;
 if(fstat(in,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1){close(in);return HB_STAGE_INVALID;}
 int out=open(output,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,!strcmp(relative,"app")?0755:0644);
 if(out<0){close(in);return HB_STAGE_IO;}
 hb_sha256_init(&hash);
 for(;;) {
  if(stopped(stop)){result=HB_STAGE_CANCELLED;break;}
  ssize_t n=read(in,buffer,sizeof buffer);
  if(n<0){if(errno==EINTR)continue;break;}
  if(!n) {
   if(total!=bytes){result=HB_STAGE_SIZE;break;}
   hb_sha256_final(&hash,digest);result=HB_STAGE_OK;
   for(unsigned i=0;i<32;i++)if(digest[i]!=expected[i]){result=HB_STAGE_HASH;break;}
   if(!result&&fsync(out))result=HB_STAGE_IO;
   break;
  }
  if((unsigned)n>bytes-total){result=HB_STAGE_SIZE;break;}
  unsigned done=0;
  while(done<(unsigned)n) {
   if(stopped(stop)){result=HB_STAGE_CANCELLED;goto finished;}
   ssize_t wrote=write(out,buffer+done,(unsigned)n-done);
   if(wrote<0&&errno==EINTR)continue;
   if(wrote<=0)goto finished;
   done+=(unsigned)wrote;
  }
  total+=(unsigned)n;hb_sha256_update(&hash,buffer,(unsigned)n);
 }
finished:
 if(close(in))result=HB_STAGE_IO;
 if(close(out))result=HB_STAGE_IO;
 return result;
}
static int sync_tree(const char *folder,unsigned depth,volatile int *stop) {
 struct dirent *entry;struct stat s;int result=0;
 if(depth>16||stopped(stop))return -1;
 DIR *dir=opendir(folder);if(!dir)return -1;
 errno=0;
 while((entry=readdir(dir))) {
  char child[512];
  if(!strcmp(entry->d_name,".")||!strcmp(entry->d_name,".."))continue;
  if(join(child,folder,entry->d_name)||lstat(child,&s)||stopped(stop)){result=-1;break;}
  if(S_ISDIR(s.st_mode)){if(sync_tree(child,depth+1,stop)){result=-1;break;}}
  else if(!S_ISREG(s.st_mode)||s.st_nlink!=1){result=-1;break;}
  errno=0;
 }
 if(errno)result=-1;
 if(closedir(dir))result=-1;
 if(!result&&sync_dir(folder))result=-1;
 return result;
}
int hb_bundle_stage(const char *source,const char *id,const char *parent,unsigned long long reserve,
                    volatile int *stop,struct hb_bundle *bundle) {
 char resolved[PATH_MAX],stage[512],name[64];struct stat s;struct statvfs space;
 unsigned long long allocation;
 if(!source||!parent||!id||!bundle)return HB_STAGE_INVALID;
 if(stopped(stop))return HB_STAGE_CANCELLED;
 if(hb_bundle_check(source,id,stop,bundle))return stopped(stop)?HB_STAGE_CANCELLED:HB_STAGE_VERIFY;
 if(!realpath(parent,resolved)||strcmp(parent,resolved)||strlen(parent)>=512||
    lstat(parent,&s)||!S_ISDIR(s.st_mode))return HB_STAGE_INVALID;
 unsigned a=(unsigned)strlen(source),b=(unsigned)strlen(parent);
 if((a<=b&&!strncmp(source,parent,a)&&(parent[a]=='/'||!parent[a]))||
    (b<=a&&!strncmp(parent,source,b)&&(source[b]=='/'||!source[b])))return HB_STAGE_INVALID;
 dev_t device=s.st_dev;
 snprintf(name,sizeof name,".install-%s",id);
 if(join(stage,parent,name))return HB_STAGE_INVALID;
 if(!lstat(stage,&s))return HB_STAGE_EXISTS;
 if(errno!=ENOENT)return HB_STAGE_IO;
 if(statvfs(parent,&space)||space.f_frsize>1048576||
    hb_bundle_allocation_bound(bundle,(unsigned)space.f_frsize,&allocation))return HB_STAGE_IO;
 if(allocation+reserve<allocation)return HB_STAGE_INVALID;
 if(space.f_bavail>~0ULL/space.f_frsize)return HB_STAGE_IO;
 if((unsigned long long)space.f_bavail*space.f_frsize<allocation+reserve)return HB_STAGE_NO_SPACE;
 if(stopped(stop))return HB_STAGE_CANCELLED;
 if(mkdir(stage,0700))return errno==EEXIST?HB_STAGE_EXISTS:HB_STAGE_IO;
 if(bundle->has_inventory) {
  int result=copy_file(source,stage,"files.sha256",bundle->inventory_bytes,bundle->inventory_sha256,device,stop);
  if(result)return result;
 }
 for(unsigned i=0;i<bundle->inventory.count;i++) {
  const struct hb_inventory_file *file=bundle->inventory.files+i;
  int result=copy_file(source,stage,file->path,file->bytes,file->sha256,device,stop);
  if(result)return result;
 }
 if(hb_bundle_check(stage,id,stop,bundle))return stopped(stop)?HB_STAGE_CANCELLED:HB_STAGE_VERIFY;
 if(sync_tree(stage,0,stop)||sync_dir(parent))return stopped(stop)?HB_STAGE_CANCELLED:HB_STAGE_IO;
 return HB_STAGE_OK;
}
