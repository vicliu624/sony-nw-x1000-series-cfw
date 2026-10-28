#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "qqmusic_preview_supervisor.h"
#include "qqmusic_preview_owners.h"
#include "../../../sdk/include/x1000/services/process.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <signal.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int supervisor_fcntl(int,int,...) __asm__("fcntl");
static int channel(int fds[2]){
 unsigned i;if(pipe(fds))return -1;
 for(i=0;i<2;i++){int flags=supervisor_fcntl(fds[i],F_GETFL);if(flags<0||supervisor_fcntl(fds[i],F_SETFL,flags|O_NONBLOCK)<0||supervisor_fcntl(fds[i],F_SETFD,FD_CLOEXEC)<0){close(fds[0]);close(fds[1]);fds[0]=fds[1]=-1;return -1;}}
 return 0;
}
int qq_preview_supervisor_run(const struct qq_preview_supervisor_config *c){
 int commands[2]={-1,-1},pcm[2]={-1,-1},status[2]={-1,-1};struct stat guard;long ui=0,parent;
 struct qq_preview_server_channels server;unsigned reaped=0,sent=0,killed=0,error=0;int ui_status=0,rc=-1;
 uint64_t now=0,previous=0,stop_at=0,ui_birth=0;unsigned ui_parent=0;
 if(!c||!c->stop||*c->stop||c->verified_guard_fd<0||!c->ui||!c->pump||!c->descendants_quiet||!c->clock||c->ui_grace_ms>30000)return -1;
 if(fstat(c->verified_guard_fd,&guard)||!S_ISREG(guard.st_mode)||guard.st_nlink!=1)return -1;
 if(hb_stop_signals_install(c->stop)||signal(SIGPIPE,SIG_IGN)==SIG_ERR||signal(SIGCHLD,SIG_DFL)==SIG_ERR||channel(commands)||channel(pcm)||channel(status))goto done;
 parent=(long)getpid();ui=hb_linux_fork();if(ui<0)goto done;
 if(!ui){
  volatile int ui_stop=0;struct qq_preview_client_channels client;int result;
  close(commands[0]);close(pcm[0]);close(status[1]);client.command=commands[1];client.pcm=pcm[1];client.status=status[0];
  if(hb_linux_prepare_child()<0||hb_stop_signals_install(&ui_stop)||hb_linux_bind_parent_stop(parent)<0||hb_linux_set_group(0,0)<0)hb_linux_exit(2);
  result=c->ui(c->context,&client,&ui_stop);close(client.command);close(client.pcm);close(client.status);hb_linux_exit(result?2:0);
 }
 close(commands[1]);commands[1]=-1;close(pcm[1]);pcm[1]=-1;close(status[0]);status[0]=-1;
 server.command=commands[0];server.pcm=pcm[0];server.status=status[1];server.ui_pid=ui;
 if(qq_preview_process_identity((unsigned)ui,&ui_parent,&ui_birth)!=1||ui_parent!=(unsigned)parent){error=1;*c->stop=1;ui_birth=0;}
 for(;;){
  int clean,quiet;long waited;
  if(c->clock(c->context,&now)||now<previous){error=1;*c->stop=1;now=previous;}previous=now;
  if(!reaped){
   waited=hb_linux_wait_nohang(ui,&ui_status);
   if(waited==ui){reaped=1;if(!WIFEXITED(ui_status)||WEXITSTATUS(ui_status))error=1;}
   else if(waited==-ECHILD){reaped=1;error=1;*c->stop=1;}
   else if(waited<0&&waited!=-EINTR){error=1;*c->stop=1;}
  }
  if(*c->stop&&!reaped&&!sent){if(hb_linux_terminate(ui)<0)error=1;sent=1;stop_at=now;}
  clean=c->pump(c->context,&server,reaped,*c->stop!=0||reaped);
  if(clean<0){error=1;*c->stop=1;}
  quiet=c->descendants_quiet(c->context);if(quiet<0){error=1;*c->stop=1;}
  if(quiet==1&&clean==1&&(reaped||*c->stop)){
   quiet=qq_preview_guard_quiet(c->verified_guard_fd,!reaped&&ui_birth?(unsigned)ui:0,!reaped?ui_birth:0);
   if(quiet<0){error=1;*c->stop=1;}
  }
  if(reaped&&clean==1&&quiet==1){rc=error?-1:0;break;}
  /* Only a real, still-owned child may be forced out, and only after the
   * audio owner and all descendants are already confirmed quiescent. */
  if(sent&&!reaped&&!killed&&c->ui_grace_ms&&now-stop_at>=c->ui_grace_ms&&clean==1&&quiet==1){if(hb_linux_kill(ui)<0)error=1;killed=1;error=1;}
  hb_linux_wait_tick();
 }
done:
 if(commands[0]>=0)close(commands[0]);
 if(commands[1]>=0)close(commands[1]);
 if(pcm[0]>=0)close(pcm[0]);
 if(pcm[1]>=0)close(pcm[1]);
 if(status[0]>=0)close(status[0]);
 if(status[1]>=0)close(status[1]);
 return rc;
}
