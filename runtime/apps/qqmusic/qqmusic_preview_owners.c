#define _XOPEN_SOURCE 700
#include "qqmusic_preview_owners.h"
#include "qqmusic_preview_handoff.h"
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int owners_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern ssize_t owners_read(int,void *,size_t) __asm__("read");
static int numeric(const char *s,unsigned *out){
 unsigned n=0;if(!*s)return -1;
 while(*s){unsigned c=(unsigned char)*s++;if(c<'0'||c>'9'||n>(2147483647u-(c-'0'))/10)return -1;n=n*10+c-'0';}
 *out=n;return n?0:-1;
}
int qq_preview_process_status(unsigned pid,unsigned *parent,uint64_t *birth,char *state){
 char path[64],data[2048];int fd,rc=-1;ssize_t n;size_t used=0;
 if(!pid||!parent||!birth||!state)return -1;
 *parent=0;*birth=0;*state=0;
 owners_snprintf(path,sizeof(path),"/proc/%u/stat",pid);fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return errno==ENOENT?0:-1;
 while(used<sizeof(data)-1){n=owners_read(fd,data+used,sizeof(data)-1-used);if(n<0&&errno==EINTR)continue;if(n<0)goto done;if(!n){data[used]=0;if(!memchr(data,0,used)&&!qq_preview_process_stat(data,pid,parent,birth)){*state=strrchr(data,')')[2];rc=1;}goto done;}used+=(size_t)n;}
done:if(close(fd))rc=-1;return rc;
}
int qq_preview_process_identity(unsigned pid,unsigned *parent,uint64_t *birth){char state;return qq_preview_process_status(pid,parent,birth,&state);}
int qq_preview_guard_quiet(int guard_fd,unsigned ui_pid,uint64_t ui_birth){
 struct stat guard,after;DIR *all;struct dirent *entry;unsigned count=0,self=(unsigned)getpid();int rc=-1;
 if(guard_fd<0||(ui_pid&&!ui_birth)||(!ui_pid&&ui_birth)||fstat(guard_fd,&guard)||!S_ISREG(guard.st_mode)||guard.st_nlink!=1)return -1;
 if(ui_pid){unsigned parent;uint64_t birth;int observed=qq_preview_process_identity(ui_pid,&parent,&birth);
  if(observed!=1)return observed;
  if(parent!=self||birth!=ui_birth)return -1;
 }
 all=opendir("/proc");if(!all)return -1;
 for(;;){
  unsigned pid,parent,parent_after,inspected=0;uint64_t birth,birth_after;char path[128];DIR *fds;struct dirent *file;int found=0,observed;
  errno=0;entry=readdir(all);if(!entry){if(!errno)rc=1;break;}
  if(numeric(entry->d_name,&pid))continue;
  if(++count>256)break;
  if(pid==self)continue;
  observed=qq_preview_process_identity(pid,&parent,&birth);if(observed!=1){rc=observed;break;}
  if(pid==ui_pid){if(birth!=ui_birth){rc=-1;break;}continue;}
  owners_snprintf(path,sizeof(path),"/proc/%u/fd",pid);fds=opendir(path);if(!fds){rc=errno==ENOENT?0:-1;break;}
  for(;;){
   unsigned number;struct stat target;
   errno=0;file=readdir(fds);if(!file){if(errno)found=-1;break;}
   if(numeric(file->d_name,&number)&&strcmp(file->d_name,"0"))continue;
   if(++inspected>256){found=-1;break;}
   owners_snprintf(path,sizeof(path),"/proc/%u/fd/%u",pid,number);
   if(stat(path,&target)){found=errno==ENOENT?2:-1;break;}
   if(S_ISREG(target.st_mode)&&target.st_dev==guard.st_dev&&target.st_ino==guard.st_ino){found=1;break;}
  }
  if(closedir(fds))found=-1;
  if(found){rc=found<0?-1:0;break;}
  observed=qq_preview_process_identity(pid,&parent_after,&birth_after);
  if(observed!=1||birth_after!=birth||parent_after!=parent){rc=observed<0?-1:0;break;}
 }
 if(closedir(all))rc=-1;
 if(fstat(guard_fd,&after)||after.st_dev!=guard.st_dev||after.st_ino!=guard.st_ino||!S_ISREG(after.st_mode)||after.st_nlink!=1)rc=-1;
 return rc;
}
