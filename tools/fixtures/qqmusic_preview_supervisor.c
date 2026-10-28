#define _DEFAULT_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_preview_supervisor.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_wire.h"
#include "../../runtime/store/deadline.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
extern void *supervisor_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
struct model {volatile unsigned audio_started,restored,returned,unlocked,early,worker_done,ui_done,ui_reaped,loops,eof_before_reap;volatile int stop;unsigned kind,after_exit;};
extern int fixture_fprintf(FILE *,const char *,...) __asm__("fprintf");
static unsigned private_account_marker;
static int guard_fd;static const char *guard_path;
static int clock_read(void *p,uint64_t *out){(void)p;
#ifdef HB_STORE_LIBC_CLOCK
 {unsigned long long n;if(hb_monotonic_millis(&n))return -1;*out=n;return 0;}
#else
 {struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));*out=(uint64_t)t.tv_sec*1000+(unsigned long)t.tv_nsec/1000000;return 0;}
#endif
}
static int ui(void *context,const struct qq_preview_client_channels *c,volatile int *stop){
 struct model *m=context;unsigned char bytes[32];struct qq_preview_record record={1,0,1,30000,QQ_PREVIEW_BEGIN};
 private_account_marker=111;assert(!qq_preview_record_encode(&record,bytes,32));assert(write(c->command,bytes,32)==32);
 if(m->kind==1){raise(SIGKILL);return 1;}
 if(m->kind==2){while(!*stop)usleep(1000);}
 if(m->kind==3){assert(signal(SIGTERM,SIG_IGN)!=SIG_ERR);for(;;)usleep(1000);}
 if(m->kind==4){long child=fork();assert(child>=0);if(!child){usleep(150000);assert(!close(guard_fd));m->worker_done=1;_exit(0);}}
 if(m->kind==5){assert(!close(c->command));usleep(100000);}
 m->ui_done=1;return 0;
}
static int pump(void *context,const struct qq_preview_server_channels *c,unsigned reaped,unsigned stopped){
 struct model *m=context;unsigned char bytes[32];ssize_t n;struct qq_preview_record r;
 assert(!private_account_marker);m->loops++;n=read(c->command,bytes,32);
 if(n==32){assert(!qq_preview_record_decode(bytes,32,1,1,&r));m->audio_started=1;}
 else if(!n&&!reaped)m->eof_before_reap=1;
 else if(n<0)assert(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR);
 if((m->kind==2||m->kind==3)&&m->loops>=5)m->stop=1;
 if(reaped){m->ui_reaped=1;m->after_exit++;}
 if((stopped||reaped)&&m->audio_started){
  if(m->kind==6&&m->after_exit<3)return -1;
  if(m->after_exit>=8||m->kind==3){m->restored=1;return 1;}
  return 0;
 }
 return m->audio_started?0:1;
}
/* Intentionally optimistic callback: production's mandatory FD scan must still
 * prevent retirement while the orphan retains the inherited guard. */
static int quiet(void *context){(void)context;return 1;}
static long observer(struct model *m){
 long pid=fork();assert(pid>=0);if(!pid){unsigned ticks=0;int fd;assert(!close(guard_fd));
  while(!m->returned&&ticks++<10000){fd=open(guard_path,O_RDWR);assert(fd>=0);if(!flock(fd,LOCK_EX|LOCK_NB)){if(!m->returned){m->early=1;_exit(1);}m->unlocked=1;close(fd);_exit(0);}assert(errno==EWOULDBLOCK||errno==EAGAIN);close(fd);usleep(1000);}
  for(ticks=0;ticks<10000;ticks++){fd=open(guard_path,O_RDWR);assert(fd>=0);if(!flock(fd,LOCK_EX|LOCK_NB)){m->unlocked=1;close(fd);_exit(0);}close(fd);usleep(1000);}_exit(2);
 }return pid;
}
int main(int argc,char **argv){
 struct model *m;unsigned kind;assert(argc==2);guard_path=argv[1];
 m=supervisor_mmap(0,sizeof(*m),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);assert(m!=MAP_FAILED);
 for(kind=0;kind<7;kind++){
  struct qq_preview_supervisor_config config;long watched;int result,status;
  memset(m,0,sizeof(*m));m->kind=kind;private_account_marker=0;guard_fd=open(guard_path,O_RDWR|O_CREAT,0600);assert(guard_fd>=0&&!flock(guard_fd,LOCK_EX|LOCK_NB));watched=observer(m);
  memset(&config,0,sizeof(config));config.context=m;config.stop=&m->stop;config.verified_guard_fd=guard_fd;config.ui=ui;config.pump=pump;config.descendants_quiet=quiet;config.clock=clock_read;config.ui_grace_ms=100;
  result=qq_preview_supervisor_run(&config);assert(m->ui_reaped&&m->restored&&!m->early);assert(!private_account_marker);
  if(kind==1||kind==3||kind==6)assert(result<0);else assert(!result);
  if(kind==4)assert(m->worker_done);
  if(kind==5)assert(m->eof_before_reap);
  m->returned=1;assert(!close(guard_fd));{long got;do{got=waitpid((pid_t)watched,&status,0);}while(got<0&&errno==EINTR);if(got!=watched||!WIFEXITED(status)||WEXITSTATUS(status)||!m->unlocked||m->early)fixture_fprintf(stderr,"kind %u got %ld status %d unlocked %u early %u errno %d\n",kind,got,status,m->unlocked,m->early,errno);assert(got==watched&&WIFEXITED(status)&&!WEXITSTATUS(status)&&m->unlocked&&!m->early);}
 }
 assert(!munmap(m,sizeof(*m)));return 0;
}





