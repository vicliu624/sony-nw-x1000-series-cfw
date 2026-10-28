#define _XOPEN_SOURCE 700
#include "qqmusic_preview_client.h"
#include "qqmusic_preview_wire.h"
#include "qqmusic_preview_session.h"
#include "qqmusic_preview_owners.h"
#include "../../native/linux_process.h"
#include "../../native/linux_signals.h"
#include "../../store/deadline.h"
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int client_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t client_read(int,void *,size_t) __asm__("read");
extern ssize_t client_write(int,const void *,size_t) __asm__("write");
static int queue(struct qq_preview_client *c,unsigned type,unsigned argument,uint64_t value){
 struct qq_preview_record r;
 if(c->queued>=3||!c->command_sequence||c->command_sequence==UINT32_MAX)return -1;
 r.generation=c->generation;r.sequence=c->command_sequence;r.type=type;r.argument=argument;r.value=value;
 if(qq_preview_record_encode(&r,c->commands+c->queued*32,32))return -1;
 c->queued++;c->command_sequence++;return 0;
}
static int pipe_fd(int fd,unsigned writing){struct stat s;int flags=client_fcntl(fd,F_GETFL);return fd<0||flags<0||!(flags&O_NONBLOCK)||((flags&O_ACCMODE)==O_RDONLY)==writing||fstat(fd,&s)||!S_ISFIFO(s.st_mode)?-1:0;}
int qq_preview_client_init(struct qq_preview_client *c,const struct qq_preview_client_channels *channels,volatile int *stop){
 if(!c||!channels||!stop||*stop||getppid()<=1||pipe_fd(channels->command,1)||pipe_fd(channels->pcm,1)||pipe_fd(channels->status,0))return -1;
 memset(c,0,sizeof(*c));c->channels=*channels;c->stop=stop;c->root=(unsigned)getppid();c->command_sequence=c->status_sequence=1;c->gate=-1;c->reaped=1;c->initialized=1;return 0;
}
static void source_child(struct qq_preview_client *c,int gate,int gate_writer,unsigned parent,uint64_t generation,unsigned ms,qq_preview_worker_entry entry,void *context){
 volatile int stop=0;struct qq_preview_worker_job job;struct hb_transfer_deadline deadline;unsigned wait;char go=0;int rc;
 close(gate_writer);close(c->channels.command);close(c->channels.status);
 if(hb_linux_prepare_child()<0||hb_stop_signals_install(&stop)||hb_linux_bind_parent_stop(parent)<0||hb_transfer_deadline_init(&deadline,30000))hb_linux_exit(2);
 while(!stop&&(unsigned)getppid()==parent){
  ssize_t n=client_read(gate,&go,1);
  if(n==1)break;
  if(!n)hb_linux_exit(0);
  if(!(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR)||hb_transfer_deadline_remaining(&deadline,&wait)!=1)hb_linux_exit(2);
  hb_linux_wait_tick();
 }
 close(gate);
 if(stop||(unsigned)getppid()!=parent||go!='G')hb_linux_exit(0);
 job.pcm_fd=c->channels.pcm;job.generation=generation;job.maximum_ms=ms;job.stop=&stop;
 rc=entry(context,&job);close(job.pcm_fd);hb_linux_exit(rc&&rc!=-2?2:0);
}
int qq_preview_client_begin(struct qq_preview_client *c,unsigned ms,qq_preview_worker_entry entry,void *context){
 int gate[2];long child;unsigned parent;uint64_t birth;
 if(!c||!c->initialized||c->active||!c->reaped||c->queued||*c->stop||!entry||!ms||ms>30000||c->generation==UINT64_MAX||c->command_sequence>UINT32_MAX-3)return -1;
 if(pipe(gate))return -1;
 if(client_fcntl(gate[0],F_SETFL,O_NONBLOCK)<0||client_fcntl(gate[1],F_SETFL,O_NONBLOCK)<0||client_fcntl(gate[0],F_SETFD,FD_CLOEXEC)<0||client_fcntl(gate[1],F_SETFD,FD_CLOEXEC)<0){close(gate[0]);close(gate[1]);return -1;}
 parent=(unsigned)getpid();child=hb_linux_fork();if(child<0){close(gate[0]);close(gate[1]);return -1;}
 if(!child)source_child(c,gate[0],gate[1],parent,c->generation+1,ms,entry,context);
 close(gate[0]);c->worker=(unsigned)child;c->gate=gate[1];c->generation++;c->maximum_ms=ms;c->frames=0;
 c->active=1;c->reaped=c->started=c->cancelled=c->failed=c->stop_queued=c->signalled=c->killed=c->bind_sent=0;c->phase=QQ_PREVIEW_ACQUIRING;c->flags=0;c->stop_at=0;
 if(queue(c,QQ_PREVIEW_BEGIN,ms,0)||qq_preview_process_identity(c->worker,&parent,&birth)!=1||parent!=(unsigned)getpid()||queue(c,QQ_PREVIEW_BIND,c->worker,birth)){c->failed=1;(void)qq_preview_client_stop(c);}
 return 0;
}
int qq_preview_client_stop(struct qq_preview_client *c){
 if(!c||!c->initialized)return -1;
 if(!c->active)return 0;
 c->cancelled=1;
 if(!c->bind_sent){
  unsigned i;for(i=0;i<c->queued;i++)if(c->commands[i*32+5]==QQ_PREVIEW_BIND){memmove(c->commands+i*32,c->commands+(i+1)*32,(c->queued-i-1)*32);c->queued--;c->command_sequence--;break;}
  if(c->gate>=0){close(c->gate);c->gate=-1;}
 }
 if(!c->stop_queued){if(queue(c,QQ_PREVIEW_STOP,0,0))return -1;c->stop_queued=1;}
 return 0;
}
static void stop_worker(struct qq_preview_client *c,uint64_t now){
 if(!c->cancelled||c->reaped||(!c->started&&c->bind_sent&&c->phase<QQ_PREVIEW_STOPPING&&(unsigned)getppid()==c->root))return;
 if(!c->signalled){if(hb_linux_terminate(c->worker)<0)c->failed=1;c->signalled=1;c->stop_at=now;}
 else if(!c->killed&&now-c->stop_at>=3000){if(hb_linux_kill(c->worker)<0)c->failed=1;c->killed=1;c->failed=1;}
}
static int status(struct qq_preview_client *c){
 struct qq_preview_record r;ssize_t n=client_read(c->channels.status,c->status+c->status_used,32-c->status_used);
 if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR))return 0;
 if(n<=0)return -1;
 c->status_used+=(unsigned)n;if(c->status_used<32)return 0;
 if(qq_preview_record_decode(c->status,32,c->generation,c->status_sequence,&r)||c->status_sequence==UINT32_MAX||r.value>(uint64_t)c->maximum_ms*44100u/1000u)return -1;
 c->status_sequence++;c->status_used=0;c->phase=r.argument&255u;c->flags=r.argument&~255u;c->frames=r.value;if(c->flags&0x400u)c->failed=1;
 if(c->phase>=QQ_PREVIEW_STOPPING){c->cancelled=1;if(c->gate>=0){close(c->gate);c->gate=-1;}}
 else if((c->flags&0x100u)&&!c->started&&!c->cancelled){
  if(c->gate<0||client_write(c->gate,"G",1)!=1)return -1;
  close(c->gate);c->gate=-1;c->started=1;
 }
 return 0;
}
int qq_preview_client_poll(struct qq_preview_client *c,uint64_t now){
 long waited;ssize_t n;
 if(!c||!c->initialized)return -1;
 if(now<c->last_ms){c->failed=1;(void)qq_preview_client_stop(c);now=c->last_ms;}c->last_ms=now;
 if(!c->active)return 1;
 if(*c->stop)(void)qq_preview_client_stop(c);
 if(!c->reaped){waited=hb_linux_wait_nohang(c->worker,&c->worker_status);
  if(waited==(long)c->worker){c->reaped=1;if((!WIFEXITED(c->worker_status)||WEXITSTATUS(c->worker_status))&&!(c->cancelled&&WIFSIGNALED(c->worker_status)&&WTERMSIG(c->worker_status)==SIGTERM))c->failed=1;}
  else if(waited==-ECHILD){c->reaped=1;c->failed=1;}
  else if(waited<0&&waited!=-EINTR)c->failed=1;
 }
 if(c->queued){
  n=client_write(c->channels.command,c->commands,32);
  if(n==32){if(c->commands[5]==QQ_PREVIEW_BIND)c->bind_sent=1;c->queued--;memmove(c->commands,c->commands+32,c->queued*32);}
  else if(n>=0||!(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR)){c->failed=1;(void)qq_preview_client_stop(c);stop_worker(c,now);return -1;}
 }
 if(status(c)){c->failed=1;(void)qq_preview_client_stop(c);stop_worker(c,now);return -1;}
 stop_worker(c,now);
 if(c->phase==QQ_PREVIEW_REVIEW)return -1;
 if(c->phase==QQ_PREVIEW_DONE&&c->reaped&&!c->queued){c->active=0;return 1;}
 return 0;
}
