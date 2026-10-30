#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_owner_stream.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int stream_fcntl(int,int,...) __asm__("fcntl");
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static void erase(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int identity(const struct xnow_owner_stream *s,unsigned i){
 struct stat st;int fd=i?s->output:s->input,flags=stream_fcntl(fd,F_GETFL);
 return fd>=0&&flags>=0&&(flags&O_NONBLOCK)&&(flags&O_ACCMODE)==(i?O_WRONLY:O_RDONLY)&&!fstat(fd,&st)&&S_ISFIFO(st.st_mode)&&(uint64_t)st.st_dev==s->device[i]&&(uint64_t)st.st_ino==s->inode[i];
}
static int fail(struct xnow_owner_stream *s){
 s->fault=1;erase(s->request,sizeof s->request);erase(s->response,sizeof s->response);s->used=s->output_bytes=s->written=0;
 if(!s->commands->stopped){s->commands->stopped=1;s->commands->stop(s->commands->context);}
 return XNOW_IO;
}
int xnow_owner_stream_open(struct xnow_owner_stream *s,struct xnow_owner_commands *c,int input,int output){
 if(!s||!c||!c->endpoint||!c->stop||input<0||output<0||input==output)return XNOW_ARGUMENT;
 memset(s,0,sizeof *s);s->input=s->output=-1;s->pid=(int)getpid();s->commands=c;s->needed=16;
 int original[2]={input,output};
 for(unsigned i=0;i<2;i++){
  struct stat st;int flags=stream_fcntl(original[i],F_GETFL);
  if(flags<0||!(flags&O_NONBLOCK)||(flags&O_ACCMODE)!=(i?O_WRONLY:O_RDONLY)||fstat(original[i],&st)||!S_ISFIFO(st.st_mode))goto invalid;
  s->device[i]=(uint64_t)st.st_dev;s->inode[i]=(uint64_t)st.st_ino;
  int fd=stream_fcntl(original[i],F_DUPFD,3);if(fd<0)goto invalid;
  if(i)s->output=fd;else s->input=fd;
  if(stream_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||!identity(s,i))goto invalid;
 }
 if(s->device[0]==s->device[1]&&s->inode[0]==s->inode[1])goto invalid;
 return 0;
invalid:
 if(s->input>=0)close(s->input);
 if(s->output>=0)close(s->output);
 s->input=s->output=-1;s->fault=1;return XNOW_IDENTITY;
}
int xnow_owner_stream_step(struct xnow_owner_stream *s){
 if(!s||!s->commands||s->pid!=(int)getpid())return XNOW_ARGUMENT;
 if(s->fault)return XNOW_IO;
 if(!identity(s,0)||!identity(s,1))return fail(s);
 struct pollfd p[2]={{s->input,POLLIN,0},{s->output,POLLOUT,0}};int polled=poll(p,2,0);
 if(polled<0)return errno==EINTR?XNOW_PENDING:fail(s);
 if((p[0].revents|p[1].revents)&(POLLHUP|POLLERR|POLLNVAL))return fail(s);
 if(s->output_bytes){
  if(!(p[1].revents&POLLOUT))return XNOW_PENDING;
  ssize_t n=write(s->output,s->response+s->written,s->output_bytes-s->written);
  if(n<0&&(errno==EAGAIN||errno==EINTR))return XNOW_PENDING;
  if(n<=0)return fail(s);
  s->written+=(size_t)n;
  if(s->written==s->output_bytes){erase(s->response,sizeof s->response);s->written=s->output_bytes=0;}
  return XNOW_PENDING;
 }
 if(!(p[0].revents&POLLIN))return XNOW_AGAIN;
 ssize_t n=read(s->input,s->request+s->used,s->needed-s->used);
 if(n<0&&(errno==EAGAIN||errno==EINTR))return XNOW_PENDING;
 if(n<=0)return fail(s);
 s->used+=(size_t)n;
 if(s->used<16)return XNOW_PENDING;
 if(s->needed==16){
  uint32_t bytes=get32(s->request+12);
  if(memcmp(s->request,"XNC1",4)||bytes>XNOW_OWNER_COMMAND_MAX-16)return fail(s);
  s->needed=16+bytes;
 }
 if(s->used<s->needed)return XNOW_PENDING;
 if(xnow_owner_commands_dispatch(s->commands,s->request,s->used,s->response,sizeof s->response))return fail(s);
 erase(s->request,sizeof s->request);s->used=0;s->needed=16;s->output_bytes=16;s->written=0;return XNOW_PENDING;
}
int xnow_owner_stream_writable(const struct xnow_owner_stream *s){return s&&s->commands&&s->pid==(int)getpid()&&!s->fault&&!s->output_bytes&&!s->commands->stopped;}
int xnow_owner_stream_completion(struct xnow_owner_stream *s,const struct xnow_owner_completion *e){
 if(!s||!e||!e->request)return XNOW_ARGUMENT;
 if(!xnow_owner_stream_writable(s))return XNOW_PENDING;
 memset(s->response,0,32);memcpy(s->response,"XNT1",4);put32(s->response+4,32);put32(s->response+8,e->request);put32(s->response+12,(uint32_t)e->result.result);memcpy(s->response+16,e->result.destination,6);put32(s->response+24,e->result.stock_status);put32(s->response+28,e->result.raw_fields);s->output_bytes=32;s->written=0;return 0;
}
int xnow_owner_stream_receive(struct xnow_owner_stream *s,const void *data,size_t n,const struct xnow_full_received *e){
 if(!s||!e||(!data&&n)||n>XNOW_ESPNOW_V2_MAX||e->info.payload_bytes!=n||e->info.elements>255)return XNOW_ARGUMENT;
 if(e->flags&~3u||(e->flags&3u)==3u)return XNOW_ARGUMENT;
 if(!xnow_owner_stream_writable(s))return XNOW_PENDING;
 memset(s->response,0,32);memcpy(s->response,"XNR1",4);put32(s->response+4,(uint32_t)(32+n));memcpy(s->response+12,e->source,6);s->response[18]=e->info.version;s->response[19]=(uint8_t)e->info.elements;memcpy(s->response+20,e->info.random,4);put32(s->response+24,e->flags);if(n)memcpy(s->response+32,data,n);s->output_bytes=32+n;s->written=0;return 0;
}
int xnow_owner_stream_close(struct xnow_owner_stream *s){
 if(!s||!s->commands||s->pid!=(int)getpid())return XNOW_ARGUMENT;
 int result=0;
 for(unsigned i=0;i<2;i++){int fd=i?s->output:s->input;if(fd>=0){if(!identity(s,i))result=XNOW_IDENTITY;else if(close(fd))result=XNOW_IO;}}
 erase(s->request,sizeof s->request);erase(s->response,sizeof s->response);s->input=s->output=-1;s->fault=1;return result;
}
