#define _DEFAULT_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_wifi.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <poll.h>
#include <sys/wait.h>
#include <sys/file.h>
#include <fcntl.h>
static unsigned long long clock_offset;
int hb_monotonic_millis(unsigned long long *out){struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));*out=(unsigned long long)t.tv_sec*1000+t.tv_nsec/1000000+clock_offset;return 0;}
int qq_wifi_route_ready(void){return 1;}
int main(int argc,char **argv){
 const char *cases[]={"ready","already","guardfail","connectfail","wait"};unsigned i;volatile int stopped=0;char path[4096];
 assert(argc==2);
 for(i=0;i<5;i++){
  struct qq_wifi_session s;int rc=1,pid;unsigned ticks;unsigned long long begin,end;
  assert(snprintf(path,sizeof(path),"%s/helper-%s",argv[1],cases[i])>0);qq_wifi_init(&s,path,&stopped);
  hb_monotonic_millis(&begin);assert(qq_wifi_ensure(&s)==1&&s.pid>0);hb_monotonic_millis(&end);assert(end-begin<250);pid=s.pid;
  for(ticks=0;ticks<400&&rc==1;ticks++){poll(0,0,5);if(i==4&&ticks==10)clock_offset+=45001;rc=qq_wifi_ensure(&s);}
  assert(rc==(i<2?0:-1));
  if(i==3)assert(s.error==73);
  if(i==4)assert(s.error==-4);
  qq_wifi_close(&s);assert(!s.pid&&s.read_fd==-1&&s.control_fd==-1&&kill(pid,0)<0&&errno==ESRCH&&WIFEXITED(s.wait_status));
 }
 {struct qq_wifi_session s;assert(snprintf(path,sizeof(path),"%s/helper-wait",argv[1])>0);qq_wifi_init(&s,path,&stopped);assert(qq_wifi_ensure(&s)==1);poll(0,0,25);qq_wifi_close(&s);assert(!s.pid);qq_wifi_close(&s);}
 {
  struct qq_wifi_session s;unsigned ticks;int old_pid;unsigned long long before,after;
  assert(snprintf(path,sizeof(path),"%s/helper-wait",argv[1])>0);qq_wifi_init(&s,path,&stopped);assert(qq_wifi_ensure(&s)==1);
  for(ticks=0;ticks<200&&s.phase<5;ticks++){poll(0,0,5);assert(qq_wifi_ensure(&s)==1);}
  assert(s.phase==5);poll(0,0,100);old_pid=s.pid;assert(getpgid(old_pid)==old_pid);
  hb_monotonic_millis(&before);qq_wifi_cancel(&s);hb_monotonic_millis(&after);assert(after-before<100&&s.cancelling&&s.pid==old_pid);
  assert(qq_wifi_ensure(&s)==1&&s.pid==old_pid);poll(0,0,100);assert(qq_wifi_ensure(&s)==1&&s.pid==old_pid);
  for(ticks=0;ticks<200&&s.pid==old_pid;ticks++){poll(0,0,5);assert(qq_wifi_ensure(&s)==1);}
  assert(s.pid>0&&s.pid!=old_pid&&!s.cancelling);qq_wifi_cancel(&s);qq_wifi_close(&s);assert(WIFEXITED(s.wait_status));
 }
 {
  struct qq_wifi_session s;unsigned ticks;
  assert(snprintf(path,sizeof(path),"%s/helper-wait",argv[1])>0);qq_wifi_init(&s,path,&stopped);assert(qq_wifi_ensure(&s)==1);
  for(ticks=0;ticks<200&&s.phase<5;ticks++){poll(0,0,5);assert(qq_wifi_ensure(&s)==1);}
  assert(s.phase==5);poll(0,0,100);assert(getpgid(s.pid)==s.pid&&kill(-s.pid,SIGTERM)==0);
  qq_wifi_close(&s);assert(WIFEXITED(s.wait_status)&&WEXITSTATUS(s.wait_status)==2);
 }
 {
  struct qq_wifi_session s;unsigned ticks;int lease,contender;
  assert(snprintf(path,sizeof(path),"%s/network-fixture.lock",argv[1])>0);lease=open(path,O_RDWR|O_CREAT,0600);assert(lease>=0&&flock(lease,LOCK_EX|LOCK_NB)==0);
  contender=open(path,O_RDWR);assert(contender>=0);
  assert(snprintf(path,sizeof(path),"%s/helper-wait",argv[1])>0);qq_wifi_init(&s,path,&stopped);s.lease_fd=lease;assert(qq_wifi_ensure(&s)==1);
  for(ticks=0;ticks<200&&s.phase<5;ticks++){poll(0,0,5);assert(qq_wifi_ensure(&s)==1);}
  assert(s.phase==5);poll(0,0,100);assert(close(lease)==0);
  assert(flock(contender,LOCK_EX|LOCK_NB)<0&&(errno==EAGAIN||errno==EWOULDBLOCK));
  qq_wifi_cancel(&s);assert(flock(contender,LOCK_EX|LOCK_NB)<0);qq_wifi_close(&s);
  assert(WIFEXITED(s.wait_status)&&flock(contender,LOCK_EX|LOCK_NB)==0);assert(close(contender)==0);
 }
 return 0;
}
