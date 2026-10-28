#define _DEFAULT_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_preview_transport.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_wire.h"
#include <assert.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>
#include <time.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t fixture_read(int,void *,size_t) __asm__("read");
#ifndef HB_STORE_LIBC_CLOCK
/* Host equivalent of the target's fixed-width monotonic clock boundary. */
long x1000_oabi_call(long n,long clock,long address,long a,long b,long c,long d){struct timespec t;int *out=(int *)address;(void)a;(void)b;(void)c;(void)d;assert(n==263&&clock==1);assert(!clock_gettime(CLOCK_MONOTONIC,&t));out[0]=(int)t.tv_sec;out[1]=(int)t.tv_nsec;return 0;}
#endif
static void exact(int fd,unsigned char *out,unsigned bytes){unsigned used=0;while(used<bytes){unsigned want=bytes-used;ssize_t n;if(want>5)want=5;n=fixture_read(fd,out+used,want);assert(n>0);used+=(unsigned)n;}}
int main(void){unsigned kind;for(kind=0;kind<2;kind++){
 int p[2],status;pid_t child;unsigned seq=1,used=0,packets=0;unsigned char header[32],payload[4064];
 assert(!pipe(p));assert(!fixture_fcntl(p[1],F_SETFL,O_NONBLOCK));child=fork();assert(child>=0);
 if(!child){struct qq_preview_transport t;struct qq_preview_sink sink;volatile int stop=0;unsigned char bytes[4096];unsigned i;close(p[0]);
  assert(qq_preview_transport_init(&t,p[1],1,1,&stop)<0);assert(!qq_preview_transport_init(&t,p[1],(unsigned)getppid(),1,&stop));sink=qq_preview_transport_sink(&t);
  if(kind){stop=1;assert(sink.format(sink.context,44100,2)<0);close(p[1]);_exit(0);}
  assert(!sink.format(sink.context,44100,2));for(i=0;i<4096;i++)bytes[i]=(unsigned char)i;
  assert(!sink.pcm(sink.context,bytes,4096)&&!sink.pcm(sink.context,bytes,4096));assert(t.frames==2048);
  assert(!qq_preview_transport_end(&t,0));assert(qq_preview_transport_end(&t,0)<0&&sink.pcm(sink.context,bytes,4)<0);close(p[1]);_exit(0);
 }
 close(p[1]);usleep(30000);
 if(!kind){for(;;){struct qq_preview_record r;unsigned i;exact(p[0],header,32);assert(!qq_preview_record_decode(header,32,1,seq++,&r));
   if(r.type==QQ_PREVIEW_FORMAT){assert(seq==2);continue;}
   if(r.type==QQ_PREVIEW_END){assert(!r.argument&&r.value==2048);break;}
   assert(r.type==QQ_PREVIEW_PCM);exact(p[0],payload,r.argument);for(i=0;i<r.argument;i++)assert(payload[i]==(unsigned char)(used+i));used+=r.argument;packets++;
  }assert(used==8192&&packets==4);
 }
 assert(fixture_read(p[0],header,1)==0);assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));close(p[0]);
 }return 0;}
