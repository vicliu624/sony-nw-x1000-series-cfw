#define _XOPEN_SOURCE 700
#include "qqmusic_worker.h"
#include "../../../sdk/include/x1000/services/process.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <string.h>
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
struct sender {int fd;uint32_t sequence;struct qq_runtime_import_progress last;volatile int *stop;};
static void put(unsigned char *p,uint32_t v){unsigned i;for(i=0;i<4;i++)p[i]=(unsigned char)(v>>(i*8));}
static uint32_t get(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int packet(struct sender *s,const struct qq_runtime_import_progress *p,unsigned final,unsigned failed){
 unsigned char bytes[32];ssize_t n;
 if(s->sequence==UINT32_MAX)return -1;
 put(bytes,0x51494d50);put(bytes+4,1);put(bytes+8,s->sequence+1);put(bytes+12,final);put(bytes+16,p->stage);put(bytes+20,p->percent);put(bytes+24,p->published|(p->review<<1));put(bytes+28,failed);
 do{n=write(s->fd,bytes,sizeof(bytes));}while(n<0&&errno==EINTR&&!*s->stop);
 if(n==(ssize_t)sizeof(bytes)){s->sequence++;return 1;}
 if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))return 0;
 *s->stop=1;return -1;
}
static int emit(void *context,const struct qq_runtime_import_progress *p){
 struct sender *s=context;
 if(!p||*s->stop||p->stage>3||p->percent>100||p->published>1||p->review>1||p->stage<s->last.stage||p->percent<s->last.percent){*s->stop=1;return -1;}
 s->last=*p;return packet(s,p,0,0)<0?-1:0;
}
static void child(struct qq_worker_import *w,int fd) __attribute__((noreturn));
static void child(struct qq_worker_import *w,int fd){
 volatile int stopped=0;struct sender sender;int result=-1,failed;unsigned attempts;
 memset(&sender,0,sizeof(sender));sender.fd=fd;sender.stop=&stopped;
 if(hb_linux_prepare_child()<0||hb_stop_signals_install(&stopped)<0||signal(SIGPIPE,SIG_IGN)==SIG_ERR)goto done;
 if(w->child_detach(w->application)<0||stopped)goto done;
 if(hb_linux_set_group(0,0)<0)goto done;
 result=w->run(w->application,&w->request,emit,&sender,&stopped);
done:
 failed=stopped||result!=0||!sender.last.published||sender.last.review||sender.last.stage!=3||sender.last.percent!=100;
 qq_secret_clear(&w->request,sizeof(w->request));
 for(attempts=0;attempts<100;attempts++){int rc=packet(&sender,&sender.last,1,(unsigned)failed);if(rc>0)break;if(rc<0||stopped)break;hb_linux_wait_tick();}
 close(fd);hb_linux_exit(failed?1:0);
}
static void signal_child(long pid,int hard){if(hard){if(hb_linux_kill(-pid)<0)(void)hb_linux_kill(pid);}else if(hb_linux_terminate(-pid)<0)(void)hb_linux_terminate(pid);}
void qq_worker_import_cancel(struct qq_worker_import *w){
 unsigned ticks=0;int sent=0,hard=0;if(!w)return;
 if(w->network_waiting){w->network_waiting=0;if(w->cancel_network)w->cancel_network(w->network_context);}
 while(w->pid>0){long rc=hb_linux_wait_nohang(w->pid,&w->status);if(rc==w->pid){w->pid=0;w->reaped=1;break;}if(rc==-ECHILD){w->pid=0;w->reaped=1;w->failed=1;break;}
  if(!sent){signal_child(w->pid,0);sent=1;}if(ticks>=100&&!hard){signal_child(w->pid,1);hard=1;}hb_linux_wait_tick();if(ticks<100)ticks++;
 }
 if(w->read_fd>=0){close(w->read_fd);w->read_fd=-1;}qq_secret_clear(&w->request,sizeof(w->request));qq_secret_clear(w->message,sizeof(w->message));w->used=0;
}
static int launch_worker(struct qq_worker_import *w){
 int fds[2],i;long pid;
 if(pipe(fds))goto failed;
 for(i=0;i<2;i++){int flags=sony_fcntl(fds[i],F_GETFL,0);if(flags<0||sony_fcntl(fds[i],F_SETFL,flags|O_NONBLOCK)<0||sony_fcntl(fds[i],F_SETFD,FD_CLOEXEC)<0){close(fds[0]);close(fds[1]);goto failed;}}
 pid=hb_linux_fork();if(pid<0){close(fds[0]);close(fds[1]);goto failed;}
 if(!pid){close(fds[0]);child(w,fds[1]);}
 close(fds[1]);w->read_fd=fds[0];w->pid=pid;(void)hb_linux_set_group(pid,pid);qq_secret_clear(&w->request,sizeof(w->request));return 0;
failed:qq_secret_clear(&w->request,sizeof(w->request));return -1;
}
static int begin(void *context,const struct qq_song *song,const struct qq_resource_intent *intent,const struct qq_resource *resource,const struct qq_export_plan *layout,uint64_t now,uint64_t expires){
 struct qq_worker_import *w=context;
 if(w->pid>0||w->read_fd>=0||w->network_waiting||!song||!intent||!resource||!layout||expires<=now||(w->network_stop&&*w->network_stop))return -1;
 memset(&w->progress,0,sizeof(w->progress));w->sequence=w->used=0;w->reaped=w->status=w->final_seen=w->final_failed=w->eof=w->failed=0;
 w->request.song=*song;w->request.intent=*intent;w->request.resource=*resource;w->request.layout=*layout;w->request.now_ms=now;w->request.expires_ms=expires;
 if(w->prepare_network){if(!w->cancel_network||!w->network_stop){qq_secret_clear(&w->request,sizeof(w->request));return -1;}w->network_waiting=1;return 0;}
 return launch_worker(w);
}
static int message(struct qq_worker_import *w){
 uint32_t sequence=get(w->message+8),kind=get(w->message+12),stage=get(w->message+16),percent=get(w->message+20),flags=get(w->message+24),failed=get(w->message+28);
 if(get(w->message)!=0x51494d50||get(w->message+4)!=1||w->sequence==UINT32_MAX||sequence!=w->sequence+1||kind>1||stage>3||percent>100||flags>3||failed>1||w->final_seen||stage<w->progress.stage||percent<w->progress.percent||(!kind&&failed))return -1;
 w->sequence=sequence;w->progress.stage=stage;w->progress.percent=percent;w->progress.published=flags&1;w->progress.review=(flags>>1)&1;
 if(kind){w->final_seen=1;w->final_failed=(int)failed;}return 0;
}
static int poll_worker(void *context,uint64_t now,struct qq_runtime_import_progress *out){
 struct qq_worker_import *w=context;unsigned count;if(!out)return -1;memset(out,0,sizeof(*out));
 if(w->network_waiting){
  int rc;
  if(*w->network_stop||now<w->request.now_ms||now>=w->request.expires_ms){qq_worker_import_cancel(w);return -1;}
  rc=w->prepare_network(w->network_context);
  if(*w->network_stop||rc<0){qq_worker_import_cancel(w);return -1;}
  if(rc==1)return 0;
  if(rc!=0){qq_worker_import_cancel(w);return -1;}
  w->network_waiting=0;w->request.now_ms=now;
  if(launch_worker(w))return -1;
 }
 if(w->read_fd<0)return -1;
 for(count=0;count<64&&!w->eof;count++){ssize_t n=sony_read(w->read_fd,w->message+w->used,sizeof(w->message)-w->used);
  if(n<0){if(errno==EINTR)continue;if(errno==EAGAIN||errno==EWOULDBLOCK)break;w->failed=1;break;}if(!n){w->eof=1;if(w->used)w->failed=1;break;}
  w->used+=(unsigned)n;if(w->used==sizeof(w->message)){if(message(w)){w->failed=1;break;}w->used=0;}
 }
 if(w->pid>0){long rc=hb_linux_wait_nohang(w->pid,&w->status);if(rc==w->pid){w->pid=0;w->reaped=1;}else if(rc<0&&rc!=-EINTR){w->failed=1;if(rc==-ECHILD){w->pid=0;w->reaped=1;}}}
 *out=w->progress;
 if(w->failed){out->published=0;out->review=1;return -1;}
 if(!w->reaped||!w->eof){out->published=0;return 0;}
 if(!w->final_seen||w->status!=0){out->published=0;out->review=w->progress.review||w->progress.published||!w->final_seen||(w->status!=256);return -1;}
 if(w->final_failed||!out->published||out->review||out->stage!=3||out->percent!=100){out->published=0;return -1;}return 1;
}
static void cancel(void *context){qq_worker_import_cancel(context);}
int qq_worker_import_init(struct qq_worker_import *w,qq_worker_run run,int (*detach)(void *),void *application){
 if(!w||!run||!detach)return -1;
 memset(w,0,sizeof(*w));w->read_fd=-1;w->run=run;w->child_detach=detach;w->application=application;
 w->operations.context=w;w->operations.begin=begin;w->operations.poll=poll_worker;w->operations.cancel=cancel;return 0;
}
const struct qq_runtime_import_ops *qq_worker_import_operations(struct qq_worker_import *w){return w?&w->operations:0;}
