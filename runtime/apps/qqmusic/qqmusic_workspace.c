#define _GNU_SOURCE
#include "qqmusic_workspace.h"
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern int sony_flock(int,int) __asm__("flock");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
void qq_workspace_init(struct qq_workspace *w){memset(w,0,sizeof(*w));qq_volume_init(&w->volume);w->lock=-1;}
int qq_workspace_close(struct qq_workspace *w){int rc=0;if(!w)return -1;if(w->lock>=0){if(close(w->lock))rc=-1;w->lock=-1;}if(qq_volume_close(&w->volume))rc=-1;return rc;}
int qq_workspace_check(void *context){
 struct qq_workspace *w=context;struct qq_storage_plan plan;struct stat st;uint64_t required;char path[128];int n;
 if(!w||!w->stop||*w->stop||w->lock<0)return -1;
 memset(&plan,0,sizeof(plan));
 if(qq_volume_recheck(&w->volume,&plan,&required))return -1;
 if(fstat(w->lock,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||(uint64_t)st.st_dev!=w->volume.device||(uint64_t)st.st_ino!=w->inode)return -1;
 n=sony_snprintf(path,sizeof(path),"/proc/self/fd/%d/.import.lock",w->volume.directory);
 if(n<0||(size_t)n>=sizeof(path)||lstat(path,&st)||!S_ISREG(st.st_mode)||(uint64_t)st.st_ino!=w->inode||(uint64_t)st.st_dev!=w->volume.device)return -1;
 return 0;
}
int qq_workspace_open(struct qq_workspace *w,const struct qq_storage_policy *policy,volatile int *stop){
 struct qq_storage_plan plan;uint64_t required;struct stat st;char path[128];int n,rc=-1;
 if(!w||!policy||!stop||*stop||w->lock>=0)return -1;
 w->stop=stop;memset(&plan,0,sizeof(plan));plan.metadata=4096;plan.files[5]=1;plan.reserve=1048576;
 if(qq_volume_open(&w->volume,policy,"/contents/HOMEBREW/data/qqmusic",&plan,&required))goto done;
 n=sony_snprintf(path,sizeof(path),"/proc/self/fd/%d/.import.lock",w->volume.directory);
 if(n<0||(size_t)n>=sizeof(path))goto done;
 w->lock=open(path,O_RDWR|O_CREAT|O_NOFOLLOW,0600);if(w->lock<0)goto done;
 if(sony_fcntl(w->lock,F_SETFD,FD_CLOEXEC)<0||fstat(w->lock,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||(uint64_t)st.st_dev!=w->volume.device||sony_flock(w->lock,LOCK_EX|LOCK_NB))goto done;
 w->inode=st.st_ino;rc=qq_workspace_check(w);
done:if(rc)qq_workspace_close(w);return rc;
}
