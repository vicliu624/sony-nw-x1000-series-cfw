#define _DEFAULT_SOURCE
#define main device_fixture_main
#include "qqmusic_preview_device.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_preview_client.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_service.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_transport.h"
#include <sys/wait.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
extern void *fixture_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
static volatile unsigned *started;
static struct qq_preview_service service;
#ifndef HB_STORE_LIBC_CLOCK
long x1000_oabi_call(long n,long clock,long address,long a,long b,long c,long d){struct timespec t;int *out=(int *)address;(void)a;(void)b;(void)c;(void)d;assert(n==263&&clock==1);assert(!clock_gettime(CLOCK_MONOTONIC,&t));out[0]=(int)t.tv_sec;out[1]=(int)t.tv_nsec;return 0;}
#endif
static int producer_callback(void *p,uint64_t generation){(void)p;return qq_preview_service_producer_exited(&service,generation);}
static int worker(void *context,const struct qq_preview_worker_job *job){
 unsigned kind=(unsigned)(uintptr_t)context,i;struct qq_preview_transport t;struct qq_preview_sink sink;unsigned char bytes[32];(*started)++;
 if(kind==4)return -1;
 assert(!qq_preview_transport_init(&t,job->pcm_fd,(unsigned)getppid(),job->generation,job->stop));sink=qq_preview_transport_sink(&t);
 assert(!sink.format(sink.context,44100,2));for(i=0;i<32;i++)bytes[i]=(unsigned char)i;assert(!sink.pcm(sink.context,bytes,32));
 if(kind==3){while(!*job->stop)usleep(1000);return -2;}
 return qq_preview_transport_end(&t,0);
}
static void ui(int commands,int pcm,int status,unsigned kind){
 struct qq_preview_client c;struct qq_preview_client_channels channels={commands,pcm,status};volatile int stop=0;unsigned round;
 assert(!qq_preview_client_init(&c,&channels,&stop));
 for(round=0;round<(kind==5?2u:1u);round++){
  unsigned tick,which=kind==5?(round?0:4):kind;int cancelled=0;
  assert(!qq_preview_client_begin(&c,30000,worker,(void *)(uintptr_t)which));assert(qq_preview_client_begin(&c,30000,worker,0)<0);
  if(which==1){assert(!qq_preview_client_stop(&c));cancelled=1;}
  for(tick=0;tick<5000;tick++){
   int rc=qq_preview_client_poll(&c,(uint64_t)round*10000+tick+100);assert(rc>=0);
   if(!cancelled&&((which==2&&c.bind_sent&&!c.started)||(which==3&&c.phase==QQ_PREVIEW_PLAYING))){assert(!qq_preview_client_stop(&c));cancelled=1;}
   if(rc==1)break;
   usleep(1000);
  }
  assert(tick<5000&&c.reaped&&!c.active&&c.phase==QQ_PREVIEW_DONE);
  if(which==1||which==2)assert(!*started&&!c.started);
  if(which==0||which==1||which==2||which==3)assert(!c.failed);
  if(which==4)assert(c.failed);
 }
 _exit(0);
}
int main(void){unsigned kind;assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);started=fixture_mmap(0,sizeof(*started),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);assert(started!=MAP_FAILED);
 for(kind=0;kind<6;kind++){
  int commands[2],pcm[2],statuses[2],child_status=0;pid_t child;unsigned tick,reaped=0;struct qq_preview_server_channels c;struct qq_preview_device_io io;
  *started=0;setup();io=d.io;io.producer_exited=producer_callback;assert(!qq_preview_service_init(&service,&io));assert(!pipe(commands)&&!pipe(pcm)&&!pipe(statuses));
  assert(!fixture_fcntl(commands[0],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(commands[1],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(pcm[0],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(pcm[1],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(statuses[0],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(statuses[1],F_SETFL,O_NONBLOCK));
  child=fork();assert(child>=0);if(!child){close(commands[0]);close(pcm[0]);close(statuses[1]);ui(commands[1],pcm[1],statuses[0],kind);}
  close(commands[1]);close(pcm[1]);close(statuses[0]);c.command=commands[0];c.pcm=pcm[0];c.status=statuses[1];c.ui_pid=child;
  for(tick=0;tick<10000;tick++){
   int rc;if(!reaped){pid_t got=waitpid(child,&child_status,WNOHANG);assert(got==0||got==child);if(got==child)reaped=1;}
   rc=qq_preview_service_pump(&service,&c,reaped,0,100+tick);assert(rc>=0);if(reaped&&rc==1)break;usleep(1000);
  }
  assert(tick<10000&&reaped&&WIFEXITED(child_status)&&!WEXITSTATUS(child_status));assert(service.session.phase==QQ_PREVIEW_DONE&&!m.guard&&!m.pcm&&!m.mixer);assert(!memcmp(&m.state,&m.original,sizeof(m.state)));
  close(commands[0]);close(pcm[0]);close(statuses[1]);
 }
 assert(!munmap((void *)started,sizeof(*started)));return 0;
}
