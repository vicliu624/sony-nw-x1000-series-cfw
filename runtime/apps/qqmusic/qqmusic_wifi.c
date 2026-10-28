#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "qqmusic_wifi.h"
#include "../../../sdk/include/x1000/services/clock.h"
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <signal.h>
#include <unistd.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
extern int sony_fcntl(int,int,...) __asm__("fcntl");
static int now(uint64_t *out){unsigned long long n;if(hb_monotonic_millis(&n))return -1;*out=n;return 0;}
void qq_wifi_init(struct qq_wifi_session *s,const char *helper,volatile int *stop){memset(s,0,sizeof(*s));s->helper=helper;s->stop=stop;s->read_fd=s->control_fd=s->lease_fd=-1;}
void qq_wifi_cancel(void *context){
 struct qq_wifi_session *s=context;if(!s)return;s->cancelling=1;
 if(s->control_fd>=0){close(s->control_fd);s->control_fd=-1;}
}
void qq_wifi_close(void *context){
 struct qq_wifi_session *s=context;int status;if(!s)return;
 qq_wifi_cancel(s);
 if(s->pid>0){
  /* Killing the controller can strand an original daemon request. Its EOF
   * control path cancels and drains that request, then reaps its own worker. */
  pid_t reaped;do{reaped=waitpid(s->pid,&status,0);}while(reaped<0&&errno==EINTR);
  if(reaped==s->pid)s->wait_status=status;
 }
 if(s->read_fd>=0)close(s->read_fd);
 s->pid=0;s->read_fd=s->control_fd=-1;s->phase=0;s->used=0;s->cancelling=0;
}
static int launch(struct qq_wifi_session *s,uint64_t clock){
 int response[2]={-1,-1},control[2]={-1,-1},flags;pid_t pid;
 if(pipe(response)||pipe(control))goto failed;
 flags=sony_fcntl(response[0],F_GETFL,0);if(flags<0||sony_fcntl(response[0],F_SETFL,flags|O_NONBLOCK)<0)goto failed;
 if(sony_fcntl(response[0],F_SETFD,FD_CLOEXEC)<0||sony_fcntl(control[1],F_SETFD,FD_CLOEXEC)<0)goto failed;
 pid=fork();if(pid<0)goto failed;
 if(!pid){
  int a=sony_fcntl(response[1],F_DUPFD,10),b=sony_fcntl(control[0],F_DUPFD,10),lease=s->lease_fd>=0?sony_fcntl(s->lease_fd,F_DUPFD,10):-1,fd;
  char *args[]={(char *)s->helper,"--session",0};char *environment[]={"LANG=C",0};
  /* Account-free controller drains even if the launcher later terminates the
   * QQ process group. Cancellation is its control pipe, never a group KILL. */
  if(setpgid(0,0)||*s->stop)_exit(126);
  if(a<0||b<0||dup2(a,3)<0||dup2(b,4)<0)_exit(126);
  if(s->lease_fd>=0&&(lease<0||dup2(lease,5)<0))_exit(126);
  /* Retain the verified user-workspace flock through controller drain, even
   * if the launcher terminates QQ. A new instance cannot overlap it. */
  for(fd=s->lease_fd>=0?6:5;fd<1024;fd++)close(fd);
  fd=open("/dev/null",O_RDWR);if(fd<0)_exit(126);
  if(dup2(fd,0)<0||dup2(fd,1)<0||dup2(fd,2)<0)_exit(126);
  if(fd>4)close(fd);
  execve(s->helper,args,environment);_exit(127);
 }
 (void)setpgid(pid,pid);
 close(response[1]);close(control[0]);s->pid=pid;s->read_fd=response[0];s->control_fd=control[1];s->phase=1;s->error=0;s->wait_status=0;s->used=0;s->cancelling=0;s->deadline=clock+45000;return 1;
failed:
 if(response[0]>=0)close(response[0]);
 if(response[1]>=0)close(response[1]);
 if(control[0]>=0)close(control[0]);
 if(control[1]>=0)close(control[1]);
 return -1;
}
int qq_wifi_ensure(void *context){
 struct qq_wifi_session *s=context;uint64_t clock;int status;pid_t ended;ssize_t n;
 if(!s||!s->stop||*s->stop||!s->helper||now(&clock)||clock>UINT64_MAX-45000)return -1;
 if(s->cancelling&&s->pid>0){
  ended=waitpid(s->pid,&status,WNOHANG);
  if(ended==0||(ended<0&&errno==EINTR))return 1;
  if(ended<0&&errno!=ECHILD)return -1;
  if(ended>0)s->wait_status=status;
  s->pid=0;qq_wifi_close(s);
 }
 if(!s->pid)return launch(s,clock);
 while((n=read(s->read_fd,s->packet+s->used,sizeof(s->packet)-s->used))>0){
  s->used+=(unsigned)n;
  if(s->used==sizeof(s->packet)){
   uint32_t words[3];memcpy(words,s->packet,sizeof(words));s->used=0;
   if(words[0]!=QQ_WIFI_MAGIC||words[1]<1||words[1]>7||words[1]<(unsigned)s->phase||words[2]||words[1]==7){s->error=(int32_t)words[2];qq_wifi_cancel(s);return -1;}
   s->phase=(int)words[1];
  }
 }
 if(n<0&&errno!=EAGAIN&&errno!=EINTR){qq_wifi_cancel(s);return -1;}
 ended=waitpid(s->pid,&status,WNOHANG);
 if(ended==s->pid||(ended<0&&errno==ECHILD)){if(ended>0)s->wait_status=status;s->pid=0;s->error=ended>0&&WIFEXITED(status)?WEXITSTATUS(status):-1;qq_wifi_close(s);return -1;}
 if(ended<0&&errno!=EINTR){qq_wifi_cancel(s);return -1;}
 if(!n){qq_wifi_cancel(s);return -1;}
 if(s->phase==6){
  if(clock-s->route_checked<500)return 0;
  s->route_checked=clock;
  if(qq_wifi_route_ready())return 0;
  qq_wifi_cancel(s);return -1;
 }
 if(clock>=s->deadline){s->error=-4;qq_wifi_cancel(s);return -1;}
 return 1;
}
