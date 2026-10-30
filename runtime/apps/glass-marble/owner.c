/* Foreground capability + independent full-radio owner; no application files written. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "platform.h"
#include "handoff.h"
#include "ipc.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <x1000/services/abi.h>
static volatile int stop_requested;
static void stop_signal(int n){(void)n;stop_requested=1;}
/* Pipe records <= PIPE_BUF are atomic. Slow UI drops snapshots, never recovery. */
static int emit(unsigned kind,const uint8_t *packet){
 struct gm_event e;memset(&e,0,sizeof e);e.kind=kind;if(packet){e.length=GM_PACKET;memcpy(e.packet,packet,GM_PACKET);}
 ssize_t n=write(4,&e,sizeof e);if(n==(ssize_t)sizeof e)return 0;
 if(n<0&&(errno==EAGAIN||errno==EINTR))return 1;
 stop_requested=1;return -1;
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Aqua Link full-radio owner; private --ipc only; managed launcher required.");return 0;}
 if(argc!=2||strcmp(argv[1],"--ipc"))return 64;
 struct gm_handoff h;if(gm_handoff_adopt(&h))return 69;
 long limit=sysconf(_SC_OPEN_MAX);if(limit<6)goto fail;
 for(long fd=5;fd<limit;fd++)if(fd!=h.fd)close((int)fd);
 struct stat a,b;if(fstat(3,&a)||fstat(4,&b)||!S_ISFIFO(a.st_mode)||!S_ISFIFO(b.st_mode))goto fail;
 extern int gm_fcntl(int,int,...) __asm__("fcntl");
 if(gm_fcntl(3,F_SETFL,O_NONBLOCK)<0||gm_fcntl(4,F_SETFL,O_NONBLOCK)<0)goto fail;
 if(signal(SIGPIPE,SIG_IGN)==SIG_ERR||signal(SIGTERM,stop_signal)==SIG_ERR||signal(SIGHUP,stop_signal)==SIG_ERR)goto fail;
 struct xnow_owner_gate gate;if(xnow_owner_gate_open(&gate,3,&stop_requested,0,gm_storage_guard))goto fail;
 struct xnow_full_control control;struct xnow_full_control_options options;gm_control_options(&options,&gate);
 if(xnow_full_control_init(&control,&options))goto fail;
 int prior=0,notice=GM_STARTING,bound=0;uint8_t source[6];struct gm_world last;memset(&last,0,sizeof last);
 for(;;){
  uint8_t command;ssize_t n=read(3,&command,1);if(!n||(n<0&&errno!=EAGAIN&&errno!=EINTR))stop_requested=1;
  if(n>0)stop_requested=1;
  int phase=xnow_owner_gate_step(&gate,&control);
  int state=phase==XNOW_SESSION_READY&&!stop_requested?GM_READY:phase==XNOW_SESSION_STOPPING||stop_requested?GM_RESTORING:GM_STARTING;
  if(phase<0||phase==XNOW_SESSION_REPAIR_REQUIRED)state=GM_REPAIR;
  if(state!=prior){notice=state;prior=0;}if(!prior&&emit((unsigned)notice,0)==0)prior=state;
  if(state==GM_REPAIR){for(;;)pause();} /* retain lease and restoration FD */
  if(xnow_full_control_finished(&control)){
   int failure=control.session.failure||control.session.restore_failure;
   if(xnow_owner_gate_release(&gate,&control))failure=1;
   for(unsigned i=0;i<50;i++){int r=emit(failure?GM_REPAIR:GM_FINISHED,0);if(r<=0)break;usleep(20000);}
   close(3);close(4);if(chdir("/")||gm_handoff_write(&h,(unsigned)failure))return 70;return failure?1:0;
  }
  if(state==GM_READY){
   struct xnow_endpoint *e=xnow_full_control_endpoint(&control);uint8_t bytes[1470];struct xnow_full_received info;
   int r=e?xnow_endpoint_receive(e,bytes,sizeof bytes,&info):XNOW_UNCERTAIN;
   if(!r){struct gm_world next;
    if(!gm_decode(&next,bytes,info.info.payload_bytes)&&(!bound||!memcmp(source,info.source,6))&&(!bound||next.session!=last.session||gm_newer(next.sequence,last.sequence))){
     if(!bound){memcpy(source,info.source,6);bound=1;}last=next;(void)emit(GM_FRAME,bytes);
    }
   }else if(r!=XNOW_AGAIN&&r!=XNOW_RADIO_REJECTED&&r!=XNOW_ENDPOINT_CRYPTO_UNAVAILABLE){stop_requested=1;}
  }
  usleep(10000);
 }
fail:
 close(3);close(4);if(chdir("/")||gm_handoff_startup_failed(&h))return 70;return 69;
}
