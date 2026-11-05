#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_handoff.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int handoff_fcntl(int,int,...) __asm__("fcntl");
static int pipe_identity(struct xnow_handoff *h,int fd){struct stat s;return fd>=0&&!fstat(fd,&s)&&S_ISFIFO(s.st_mode)&&(uint64_t)s.st_dev==h->device&&(uint64_t)s.st_ino==h->inode;}
static uint32_t get32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
int xnow_handoff_adopt_reader(struct xnow_handoff *h,int reader,const uint8_t cookie[16]){
 if(!h||!cookie||h->pid||h->armed||h->done||h->fault||h->used||reader<3)return XNOW_ARGUMENT;
 unsigned any=0;for(unsigned i=0;i<16;i++)any|=cookie[i];if(!any)return XNOW_ARGUMENT;
 struct stat st;int flags=handoff_fcntl(reader,F_GETFL);
 if(flags<0||(flags&O_ACCMODE)!=O_RDONLY||!(flags&O_NONBLOCK)||fstat(reader,&st)||!S_ISFIFO(st.st_mode))return XNOW_IDENTITY;
 int copy=handoff_fcntl(reader,F_DUPFD,3);if(copy<0)return XNOW_IO;
 if(handoff_fcntl(copy,F_SETFD,FD_CLOEXEC)<0){close(copy);return XNOW_IO;}
 uint8_t token[16];memcpy(token,cookie,16);
 memset(h,0,sizeof *h);h->reader=copy;h->writer=-1;h->pid=(int)getpid();h->armed=1;
 h->device=st.st_dev;h->inode=st.st_ino;memcpy(h->cookie,token,16);close(reader);return 0;
}
int xnow_handoff_create(struct xnow_handoff *h,const uint8_t cookie[16]){
 if(!h||!cookie)return XNOW_ARGUMENT;
 unsigned any=0;for(unsigned i=0;i<16;i++)any|=cookie[i];if(!any)return XNOW_ARGUMENT;
 uint8_t copy[16];memcpy(copy,cookie,16);memset(h,0,sizeof(*h));h->reader=h->writer=-1;h->pid=(int)getpid();memcpy(h->cookie,copy,16);int p[2];if(pipe(p))return XNOW_IO;
 struct stat s;if(fstat(p[0],&s)||!S_ISFIFO(s.st_mode))goto failed;h->device=s.st_dev;h->inode=s.st_ino;
 if(handoff_fcntl(p[0],F_SETFD,FD_CLOEXEC)<0||handoff_fcntl(p[1],F_SETFD,FD_CLOEXEC)<0||handoff_fcntl(p[0],F_SETFL,O_NONBLOCK)<0)goto failed;
 h->reader=p[0];h->writer=p[1];return 0;
failed:close(p[0]);close(p[1]);return XNOW_IO;
}
int xnow_handoff_child_inherit(struct xnow_handoff *h){
 if(!h||h->pid==(int)getpid()||h->armed||!pipe_identity(h,h->writer))return XNOW_IDENTITY;
 if(handoff_fcntl(h->writer,F_SETFD,0)<0)return XNOW_IO;
 if(h->reader>=0){close(h->reader);h->reader=-1;}return h->writer;
}
int xnow_handoff_parent_arm(struct xnow_handoff *h){
 if(!h||h->pid!=(int)getpid()||h->armed||!pipe_identity(h,h->reader)||!pipe_identity(h,h->writer))return XNOW_IDENTITY;
 if(close(h->writer)){h->fault=1;h->writer=-1;return XNOW_UNCERTAIN;}
 h->writer=-1;h->armed=1;return 0;
}
int xnow_handoff_poll(struct xnow_handoff *h,struct xnow_handoff_result *out){
 if(!h||!out||h->pid!=(int)getpid()||!h->armed)return XNOW_ARGUMENT;
 if(h->fault)return XNOW_UNCERTAIN;
 if(h->done){out->startup_failure=(int32_t)get32(h->record+28);return 0;}
 if(!pipe_identity(h,h->reader)){h->fault=1;return XNOW_UNCERTAIN;}
 for(;;){ssize_t n=read(h->reader,h->record+h->used,sizeof(h->record)-h->used);
  if(n<0&&errno==EINTR)continue;
  if(n<0&&errno==EAGAIN)return XNOW_PENDING;
  if(n<0){h->fault=1;return XNOW_UNCERTAIN;}
  if(!n){if(h->used==32&&!memcmp(h->record,"XRFDONE1",8)&&!memcmp(h->record+8,h->cookie,16)&&get32(h->record+24)==1){h->done=1;out->startup_failure=(int32_t)get32(h->record+28);return 0;}h->fault=1;return XNOW_UNCERTAIN;}
  h->used+=(unsigned)n;if(h->used>32){h->fault=1;return XNOW_UNCERTAIN;}
 }
}
int xnow_handoff_close(struct xnow_handoff *h){
 if(!h||h->pid!=(int)getpid())return XNOW_ARGUMENT;
 if(h->armed&&!h->done)return XNOW_UNCERTAIN;
 int result=0;
 if(h->reader>=0){if(!pipe_identity(h,h->reader)||close(h->reader))result=XNOW_UNCERTAIN;}
 if(h->writer>=0){if(!pipe_identity(h,h->writer)||close(h->writer))result=XNOW_UNCERTAIN;}
 memset(h,0,sizeof(*h));h->reader=h->writer=-1;return result;
}
