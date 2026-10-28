#define _XOPEN_SOURCE 700
#include "qqmusic_preview_producer.h"
#include "qqmusic_preview_owners.h"
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include "../../store/target_abi.h"
extern int producer_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static int executable(unsigned pid,uint64_t device,uint64_t inode){
 char path[80];struct stat image;
 producer_snprintf(path,sizeof(path),"/proc/%u/exe",pid);
 if(stat(path,&image))return errno==ENOENT?1:-1;
 return !S_ISREG(image.st_mode)||image.st_nlink!=1||image.st_dev!=device||image.st_ino!=inode?-1:0;
}
int qq_preview_producer_init(struct qq_preview_producer *p,uint64_t generation,unsigned ui,uint64_t birth){
 unsigned parent;uint64_t actual;struct stat image;char state;
 if(!p||!generation||ui<=1||!birth)return -1;
 memset(p,0,sizeof(*p));
 if(qq_preview_process_status(ui,&parent,&actual,&state)!=1||parent!=(unsigned)getpid()||actual!=birth||state=='Z'||state=='X'||stat("/proc/self/exe",&image)||!S_ISREG(image.st_mode)||image.st_nlink!=1)return -1;
 if(executable(ui,image.st_dev,image.st_ino))return -1;
 p->generation=generation;p->ui_pid=ui;p->ui_birth=birth;p->exe_device=image.st_dev;p->exe_inode=image.st_ino;return 0;
}
int qq_preview_producer_bind(struct qq_preview_producer *p,uint64_t generation,unsigned pid,uint64_t birth){
 unsigned parent,again;uint64_t actual,second;char state;
 if(!p||!generation||generation!=p->generation||p->bound||pid<=1||pid==p->ui_pid||pid==(unsigned)getpid()||!birth)return -1;
 if(qq_preview_process_identity(p->ui_pid,&parent,&actual)!=1||parent!=(unsigned)getpid()||actual!=p->ui_birth)return -1;
 if(qq_preview_process_status(pid,&parent,&actual,&state)!=1||parent!=p->ui_pid||actual!=birth||state=='Z'||state=='X'||executable(pid,p->exe_device,p->exe_inode))return -1;
 if(qq_preview_process_identity(pid,&again,&second)!=1||again!=parent||second!=actual)return -1;
 p->pid=pid;p->birth=birth;p->bound=1;return 0;
}
int qq_preview_producer_exited(struct qq_preview_producer *p,uint64_t generation){
 unsigned parent;uint64_t birth;char state;int rc;
 if(!p||!generation||generation!=p->generation||!p->bound)return -1;
 if(p->exited)return 1;
 rc=qq_preview_process_status(p->pid,&parent,&birth,&state);
 if(rc<0)return -1;
 if(!rc||birth!=p->birth||state=='Z'||state=='X'){p->exited=1;return 1;}
 {int image=executable(p->pid,p->exe_device,p->exe_inode);if(image){
  /* Exit can remove /proc/PID/exe after the first live-state read. Confirm
   * retirement again instead of treating that ordinary race as uncertainty. */
  rc=qq_preview_process_status(p->pid,&parent,&birth,&state);
  if(!rc||(rc==1&&(birth!=p->birth||state=='Z'||state=='X'))){p->exited=1;return 1;}
  /* exit_mm may remove exe while proc state still appears live. This is
   * pending, never exit confirmation; the stop deadline bounds the wait. */
  if(image==1&&rc==1&&birth==p->birth)return 0;
  return -1;
 }}
 return 0;
}
