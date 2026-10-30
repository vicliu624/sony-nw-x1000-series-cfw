#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_launcher_bridge.h"
#include "xnow_managed_process.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "../../store/target_abi.h"
int xnow_launcher_managed_mode(const struct hb_app *app){
 if(!app)return -1;
 size_t folder=strnlen(app->folder,sizeof(app->folder));if(!folder||folder==sizeof(app->folder)||strnlen(app->sha,sizeof(app->sha))!=64)return -1;
 for(unsigned i=0;i<64;i++)if(!((app->sha[i]>='0'&&app->sha[i]<='9')||(app->sha[i]>='a'&&app->sha[i]<='f')))return -1;
 char path[384];int n=snprintf(path,sizeof(path),"%s/launch.contract",app->folder);if(n<0||(unsigned)n>=sizeof(path))return -1;
 int fd=open(path,O_RDONLY|O_NONBLOCK|O_NOFOLLOW);if(fd<0)return errno==ENOENT?0:-1;
 struct stat s;char record[80];unsigned used=0;int bad=fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size!=80;
 while(!bad&&used<80){ssize_t got=read(fd,record+used,80-used);if(got<0&&errno==EINTR)continue;if(got<=0){bad=1;break;}used+=(unsigned)got;}
 if(close(fd))bad=1;
 return !bad&&!memcmp(record,"XNOW-MANAGED-1\n",15)&&!memcmp(record+15,app->sha,64)&&record[79]=='\n'?1:-1;
}
static int cookie_bytes(uint8_t out[16]){
 int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;
 struct stat s;unsigned used=0;int bad=fstat(fd,&s)||!S_ISCHR(s.st_mode);
 while(!bad&&used<16){ssize_t n=read(fd,out+used,16-used);if(n<0&&errno==EINTR)continue;if(n<=0){bad=1;break;}used+=(unsigned)n;}
 if(close(fd))bad=1;
 return bad?-1:0;
}
int xnow_launcher_run_managed(const char *directory,const char *executable,char *const env[],volatile int *stop,const struct hb_process_observer *observer){
 uint8_t cookie[16];if(cookie_bytes(cookie))return -1;
 struct xnow_managed_process process;int r=xnow_managed_process_begin(&process,directory,executable,env,stop,observer,cookie);
 if(r!=XNOW_PENDING&&r!=XNOW_UNCERTAIN)return -1;
 int logged=0;
 for(;;){
  if(observer&&observer->poll_stop)observer->poll_stop(observer->context,stop);
  struct xnow_handoff_result result;r=xnow_managed_process_poll(&process,&result);
  if(!r){int status=process.app_status;if(xnow_managed_process_close(&process))r=XNOW_UNCERTAIN;else return status;}
  if(r!=XNOW_PENDING&&!logged){fputs("Managed radio recovery is unconfirmed; foreground retained.\n",stderr);logged=1;}
  usleep(20000);
 }
}
