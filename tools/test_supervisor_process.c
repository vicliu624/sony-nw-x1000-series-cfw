#define _DEFAULT_SOURCE
#include "../runtime/apps/wireless-remote/supervisor_process.h"
#include "../runtime/platform/player/player.h"
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
static int allowed=1,deny_after;static unsigned checks;
static int admit(void *context){assert(context==&allowed);checks++;return deny_after&&(int)checks>=deny_after?0:allowed;}
static unsigned descriptors(void){DIR *d=opendir("/proc/self/fd");assert(d);unsigned count=0;struct dirent *e;while((e=readdir(d)))if(e->d_name[0]!='.')count++;assert(!closedir(d));return count;}
static void reap(struct wr_supervisor_process *p){
 for(unsigned i=0;!p->reaped;i++){assert(i<3000);int rc=wr_supervisor_process_poll(p);assert(rc==0||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNCERTAIN);usleep(1000);}
}
int main(void){
 unsigned baseline=descriptors();struct wr_supervisor_process refused={0};allowed=0;
 assert(wr_supervisor_process_start(&refused,1,&allowed,admit)==XW_PLAYER_UNAVAILABLE&&!refused.state&&descriptors()==baseline);
 allowed=2;assert(wr_supervisor_process_start(&refused,1,&allowed,admit)==XW_PLAYER_UNAVAILABLE&&descriptors()==baseline);
 allowed=1;checks=0;deny_after=2;
 assert(wr_supervisor_process_start(&refused,1,&allowed,admit)==XW_PLAYER_UNAVAILABLE&&checks==2&&descriptors()==baseline);
 deny_after=0;
 for(unsigned mode=1;mode<=2;mode++){
  struct wr_supervisor_process p={0};int extra=open("/dev/null",O_RDONLY);assert(extra>=3);
  assert(!setenv("LD_PRELOAD","/not-inherited.so",1)&&!setenv("X1000_PLAYER_INHERITED","1",1));
  assert(!wr_supervisor_process_start(&p,mode,&allowed,admit));unsetenv("LD_PRELOAD");unsetenv("X1000_PLAYER_INHERITED");
  assert(wr_supervisor_process_poll(&p)==XW_PLAYER_BUSY&&!p.reaped);
  if(mode==1)assert(!wr_supervisor_process_request_stop(&p)&&!wr_supervisor_process_request_stop(&p)&&p.stop_sent);
  assert(wr_supervisor_process_close(&p)==XW_PLAYER_BUSY);
  assert(write(p.delivery,"x",1)==1&&!wr_supervisor_process_delivery_close(&p));
  reap(&p);(void)wr_supervisor_process_poll(&p);assert(p.log_bytes==512&&p.log_tail[512]==0);
  for(unsigned i=0;i<512;i++)assert(p.log_tail[i]=='L');
  if(mode==1)assert(!p.status&&!wr_supervisor_process_close(&p)&&p.state==WR_PROCESS_CLOSED);
  else{assert(p.status==7*256&&p.state==WR_PROCESS_FAULT);assert(wr_supervisor_process_close(&p)==XW_PLAYER_BUSY);close(p.log_reader);close(p.stop_fd);}
  assert(!close(extra)&&descriptors()==baseline);
 }
 struct wr_supervisor_process p={0};assert(!wr_supervisor_process_start(&p,4,&allowed,admit));
 int reused=p.delivery;close(reused);assert(open("/dev/null",O_RDONLY)==reused);
 assert(wr_supervisor_process_delivery_close(&p)==XW_PLAYER_UNCERTAIN&&fcntl(reused,F_GETFD)>=0);
 reap(&p);assert(p.state==WR_PROCESS_FAULT&&p.status==9*256);
 close(reused);close(p.log_reader);close(p.stop_fd);assert(descriptors()==baseline);
 puts("SUPERVISOR_PROCESS_PASS");return 0;
}
