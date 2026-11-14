#define _XOPEN_SOURCE 700
#include "qqmusic_volume.h"
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t sony_readlink(const char *,char *,size_t) __asm__("readlink");
extern int sony_fstatvfs(int,struct statvfs *) __asm__("fstatvfs64");
#define QQ_VOLUME_PREFIX_LIMIT 16u
/* Export layout is at most eight levels below MUSIC; 16 includes root and
 * mount prefixes. Reject deeper input instead of allocating for 64 prefixes. */
struct observation {struct qq_storage_directory directories[QQ_VOLUME_PREFIX_LIMIT];uint64_t inodes[QQ_VOLUME_PREFIX_LIMIT];char paths[QQ_VOLUME_PREFIX_LIMIT][2049],before[65537],after[65537];};
static unsigned failure_step;
unsigned qq_volume_failure_step(void){return failure_step;}
void qq_volume_init(struct qq_volume *v){memset(v,0,sizeof(*v));v->directory=-1;}
int qq_volume_close(struct qq_volume *v){int rc=0;if(!v)return -1;if(v->directory>=0){rc=close(v->directory);v->directory=-1;}v->required=0;return rc?-1:0;}
static int mounts(char *out,size_t *length) {
 int fd=open("/proc/self/mounts",O_RDONLY|O_NOFOLLOW);size_t used=0;int rc=-1;
 if(fd<0)return -1;
 while(used<65537){ssize_t n=read(fd,out+used,65537-used);if(n<0&&errno==EINTR)continue;if(n<0||(size_t)n>65537-used)goto done;if(!n){if(used&&used<=65536){*length=used;rc=0;}goto done;}used+=(size_t)n;}
done:if(close(fd))rc=-1;return rc;
}
static int fd_path(int fd,const char *expected) {
 char link[64],actual[2049];ssize_t n;int used=sony_snprintf(link,sizeof(link),"/proc/self/fd/%d",fd);
 if(used<0||(size_t)used>=sizeof(link))return -1;
 n=sony_readlink(link,actual,sizeof(actual));if(n<0||(size_t)n>=sizeof(actual))return -1;
 actual[n]=0;return strcmp(actual,expected)?-1:0;
}
static int canonical(const char *path,size_t *length) {
 size_t i=0,start;if(!path||strncmp(path,"/contents/",10))return -1;
 while(path[i]) {
  if(i>=2048||path[i++]!='/')return -1;
  start=i;
  while(path[i]&&path[i]!='/'){unsigned char c=(unsigned char)path[i++];if(i>2048||c<32||c==127||c=='\\')return -1;}
  if(i==start||i-start>255||(i-start==1&&path[start]=='.')||(i-start==2&&path[start]=='.'&&path[start+1]=='.')||(path[i]=='/'&&!path[i+1]))return -1;
 }
 *length=i;return 0;
}
static int record(struct observation *o,unsigned index,int fd,const char *path) {
 struct stat s;
 if(fstat(fd,&s)||!S_ISDIR(s.st_mode)||!s.st_nlink||fd_path(fd,path))return -1;
 o->directories[index].path=o->paths[index];strcpy(o->paths[index],path);
 o->directories[index].device=(uint64_t)s.st_dev;o->directories[index].mode=(unsigned)s.st_mode;o->inodes[index]=(uint64_t)s.st_ino;
 return 0;
}
int qq_volume_open(struct qq_volume *v,const struct qq_storage_policy *policy,const char *path,const struct qq_storage_plan *plan,uint64_t *required) {
 struct observation *o=0;struct qq_storage_plan actual;struct statvfs space;struct stat current;
 size_t length,start,end,before=0,after=0;unsigned count=1,i;int fd=-1,next=-1,rc=QQ_STORAGE_BOUNDARY;char relative[320],prefix[2049];uint64_t peak=0;
 if(required)*required=0;
 failure_step=1;
 if(!v||v->directory>=0||!policy||!policy->source||!policy->filesystem||!plan||!required||canonical(path,&length)||strlen(policy->source)>512||strcmp(policy->filesystem,"vfat"))return QQ_STORAGE_INPUT;
 failure_step=2;o=malloc(sizeof(*o));if(!o)return QQ_STORAGE_INPUT;
 failure_step=3;
 if(mounts(o->before,&before)){rc=QQ_STORAGE_MOUNT;goto done;}
 failure_step=4;fd=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0||sony_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||record(o,0,fd,"/"))goto done;
 start=1;
 while(start<length) {
  failure_step=5;
  int written;if(count>=QQ_VOLUME_PREFIX_LIMIT)goto done;
  end=start;while(end<length&&path[end]!='/')end++;
  written=sony_snprintf(relative,sizeof(relative),"/proc/self/fd/%d/%.*s",fd,(int)(end-start),path+start);
  if(written<0||(size_t)written>=sizeof(relative))goto done;
  next=open(relative,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(next<0)goto done;
  memcpy(prefix,path,end);prefix[end]=0;
  if(sony_fcntl(next,F_SETFD,FD_CLOEXEC)<0||record(o,count,next,prefix))goto done;
  if(close(fd)){fd=-1;goto done;}fd=next;next=-1;count++;start=end+1;
 }
 failure_step=6;if(sony_fstatvfs(fd,&space)){rc=QQ_STORAGE_SPACE;goto done;}
 actual=*plan;actual.allocation_unit=(uint64_t)space.f_frsize;actual.available_units=(uint64_t)space.f_bavail;
 failure_step=7;if(mounts(o->after,&after)){rc=QQ_STORAGE_MOUNT;goto done;}
 failure_step=8;if(before!=after||memcmp(o->before,o->after,before)){rc=QQ_STORAGE_MOUNT;goto done;}
 failure_step=9;
 for(i=0;i<count;i++)if(lstat(o->paths[i],&current)||!S_ISDIR(current.st_mode)||(uint64_t)current.st_dev!=o->directories[i].device||(uint64_t)current.st_ino!=o->inodes[i])goto done;
 failure_step=10;rc=qq_storage_preflight(policy,o->before,before,o->directories,count,&actual,&peak);if(rc)goto done;
 failure_step=11;
 if(fd_path(fd,path)){rc=QQ_STORAGE_BOUNDARY;goto done;}
 v->directory=fd;fd=-1;v->device=o->directories[1].device;v->inode=o->inodes[count-1];v->system_device=o->directories[0].device;v->required=peak;
 memcpy(v->path,path,length+1);strcpy(v->source,policy->source);*required=peak;
 failure_step=0;
done:if(next>=0)close(next);if(fd>=0)close(fd);free(o);return rc;
}
int qq_volume_recheck(struct qq_volume *v,const struct qq_storage_plan *plan,uint64_t *required) {
 struct qq_volume fresh;struct qq_storage_policy policy;struct stat pinned;int rc;
 if(required)*required=0;
 if(!v||v->directory<0||!plan||!required||fstat(v->directory,&pinned)||!S_ISDIR(pinned.st_mode)||(uint64_t)pinned.st_dev!=v->device||(uint64_t)pinned.st_ino!=v->inode||fd_path(v->directory,v->path))return QQ_STORAGE_BOUNDARY;
 qq_volume_init(&fresh);policy.source=v->source;policy.filesystem="vfat";rc=qq_volume_open(&fresh,&policy,v->path,plan,required);
 if(!rc&&(fresh.device!=v->device||fresh.inode!=v->inode||fresh.system_device!=v->system_device)){*required=0;rc=QQ_STORAGE_BOUNDARY;}
 if(qq_volume_close(&fresh)&&!rc){*required=0;rc=QQ_STORAGE_BOUNDARY;}
 if(!rc)v->required=*required;
 return rc;
}
