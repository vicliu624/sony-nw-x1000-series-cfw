#define _DEFAULT_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_preview_transport.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_wire.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>
#include <time.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t fixture_read(int,void *,size_t) __asm__("read");
static unsigned char source[1048576],key[4096];static size_t source_bytes;
#ifndef __arm__
long x1000_oabi_call(long n,long clock,long address,long a,long b,long c,long d){struct timespec t;int *out=(int *)address;(void)a;(void)b;(void)c;(void)d;assert(n==263&&clock==1);assert(!clock_gettime(CLOCK_MONOTONIC,&t));out[0]=(int)t.tv_sec;out[1]=(int)t.tv_nsec;return 0;}
#endif
static int read_at(void *context,uint64_t at,unsigned char *out,unsigned n){(void)context;if(at>source_bytes||n>source_bytes-at)return -1;memcpy(out,source+(size_t)at,n);return (int)n;}
static void exact(int fd,unsigned char *out,unsigned n){unsigned used=0;while(used<n){ssize_t got=fixture_read(fd,out+used,n-used);assert(got>0);used+=(unsigned)got;}}
int main(int argc,char **argv){
 FILE *f;size_t key_bytes=0;int p[2],status;pid_t worker;uint64_t frames=0;unsigned seq=1,formatted=0;unsigned char header[32],pcm[4064];
 assert(argc==4);f=fopen(argv[1],"rb");assert(f);source_bytes=fread(source,1,sizeof(source),f);assert(source_bytes&&source_bytes<sizeof(source)&&!fclose(f));
 if(strcmp(argv[2],"-")){f=fopen(argv[2],"rb");assert(f);key_bytes=fread(key,1,sizeof(key),f);assert(key_bytes&&key_bytes<sizeof(key)&&!fclose(f));}
 assert(!pipe(p)&&!fixture_fcntl(p[1],F_SETFL,O_NONBLOCK));worker=fork();assert(worker>=0);
 if(!worker){struct qq_codec_io io={0};struct qq_preview_transport t;volatile int stop=0;close(p[0]);io.source_bytes=source_bytes;io.read_at=read_at;io.stop=&stop;
  assert(!qq_preview_transport_init(&t,p[1],(unsigned)getppid(),1,&stop));
  assert(!qq_preview_decode_worker(&t,&io,key_bytes!=0,key_bytes?(const char *)key:0,key_bytes,(unsigned)atoi(argv[3])));memset(key,0,sizeof(key));close(p[1]);_exit(0);
 }
 close(p[1]);memset(key,0,sizeof(key));usleep(30000);
 for(;;){struct qq_preview_record r;exact(p[0],header,32);assert(!qq_preview_record_decode(header,32,1,seq++,&r));
  if(r.type==QQ_PREVIEW_FORMAT){assert(!formatted&&r.argument==44100&&r.value==2);formatted=1;continue;}
  if(r.type==QQ_PREVIEW_END){assert(!r.argument&&r.value==frames);break;}
  assert(formatted&&r.type==QQ_PREVIEW_PCM);exact(p[0],pcm,r.argument);assert(fwrite(pcm,1,r.argument,stdout)==r.argument);frames+=r.argument/4u;
 }
 assert(formatted&&frames);assert(fixture_read(p[0],header,1)==0);close(p[0]);assert(waitpid(worker,&status,0)==worker&&WIFEXITED(status)&&!WEXITSTATUS(status));return 0;
}

