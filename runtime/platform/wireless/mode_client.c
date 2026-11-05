#define _DEFAULT_SOURCE
#include "mode_client.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
extern unsigned long pthread_self(void);
extern int client_fcntl(int,int,...) __asm__("fcntl");
extern int client_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern ssize_t client_send(int,const void *,size_t,int) __asm__("send");
extern ssize_t client_recv(int,void *,size_t,int) __asm__("recv");
static int owner(struct xw_mode_client *c){
 if(!c||!c->bound)return XW_MODE_INVALID;
 return c->pid!=(int)getpid()||c->thread!=pthread_self()?XW_MODE_WRONG_OWNER:0;
}
static int identity(struct xw_mode_client *c){
 struct stat s;return c->fd>=3&&!fstat(c->fd,&s)&&S_ISSOCK(s.st_mode)&&(uint64_t)s.st_dev==c->device&&(uint64_t)s.st_ino==c->inode;
}
static int fail(struct xw_mode_client *c){
 if(identity(c))close(c->fd);c->fd=-1;c->fault=1;return XW_MODE_FAULT;
}
int xw_mode_client_open(struct xw_mode_client *c,int fd,uint64_t generation){
 if(!c||c->bound||fd<3||!generation)return XW_MODE_INVALID;
 struct sockaddr_un peer;struct stat s;int type;socklen_t size=sizeof type;
 if(client_getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&size)||size!=sizeof type||type!=SOCK_DGRAM)return XW_MODE_INVALID;
 memset(&peer,0,sizeof peer);size=sizeof peer;
 if(getpeername(fd,(struct sockaddr *)&peer,&size)||size<sizeof peer.sun_family||peer.sun_family!=AF_UNIX||fstat(fd,&s)||!S_ISSOCK(s.st_mode))return XW_MODE_INVALID;
 int copy=client_fcntl(fd,F_DUPFD,3);if(copy<0)return XW_MODE_FAULT;
 if(client_fcntl(copy,F_SETFD,FD_CLOEXEC)<0||client_fcntl(copy,F_SETFL,O_NONBLOCK)<0){close(copy);return XW_MODE_FAULT;}
 memset(c,0,sizeof *c);c->generation=generation;c->pid=getpid();c->thread=pthread_self();
 c->fd=copy;c->device=s.st_dev;c->inode=s.st_ino;c->bound=1;return 0;
}
int xw_mode_client_begin(struct xw_mode_client *c,uint32_t op,int mode){
 int rc=owner(c);if(rc)return rc;if(c->fault)return XW_MODE_FAULT;
 if(c->pending)return XW_MODE_BUSY;if(c->serial==UINT64_MAX)return XW_MODE_STALE;
 unsigned char request[32];rc=xw_mode_request_encode(request,op,c->serial+1,mode);if(rc)return rc;
 memcpy(c->request,request,32);c->serial++;c->operation=op;c->pending=1;c->sent=0;return 0;
}
int xw_mode_client_step(struct xw_mode_client *c,struct xw_mode_reply *out){
 int rc=owner(c);if(rc)return rc;if(!out)return XW_MODE_INVALID;
 if(c->fault)return XW_MODE_FAULT;if(!c->pending)return XW_MODE_STALE;
 if(!identity(c))return fail(c);
 if(!c->sent){
  ssize_t n=client_send(c->fd,c->request,32,MSG_DONTWAIT|MSG_NOSIGNAL);
  if(n==32){c->sent=1;return XW_MODE_PENDING;}
  return n<0&&(errno==EAGAIN||errno==EINTR)?XW_MODE_PENDING:fail(c);
 }
 unsigned char raw[81];ssize_t n=client_recv(c->fd,raw,sizeof raw,MSG_DONTWAIT);
 if(n<0)return errno==EAGAIN||errno==EINTR?XW_MODE_PENDING:fail(c);
 if(n!=80)return fail(c);
 struct xw_mode_reply reply;rc=xw_mode_reply_decode(&reply,raw,80,c->operation,c->serial);
 if(rc==XW_MODE_STALE)return XW_MODE_PENDING;
 if(rc||reply.generation!=c->generation)return fail(c);
 memcpy(c->received,raw,80);c->owned=reply.owned;c->pending=0;*out=reply;return 0;
}
int xw_mode_client_close(struct xw_mode_client *c){
 int rc=owner(c);if(rc)return rc;
 if(c->fd>=0){if(!identity(c))return fail(c);if(close(c->fd))return fail(c);c->fd=-1;}
 c->bound=0;return c->pending||c->owned||c->fault?XW_MODE_PENDING:0;
}
