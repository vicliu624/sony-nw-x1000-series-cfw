#define _DEFAULT_SOURCE
#include "native_delivery.h"
#include "native_offer.h"
#include "../../store/deadline.h"
#include <pthread.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <fcntl.h>
#include <string.h>
#include <poll.h>
#include <errno.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
extern int delivery_fcntl(int,int,...) __asm__("fcntl");
extern int delivery_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern ssize_t delivery_send(int,const void *,size_t,int) __asm__("send");
struct delivery {int fd,pid,fault;unsigned long thread;uint64_t device,inode;};
static pthread_key_t key;static pthread_once_t once=PTHREAD_ONCE_INIT;static int initialized=-1;
static int identity(struct delivery *d){struct stat s;return d->fd>=3&&!fstat(d->fd,&s)&&S_ISSOCK(s.st_mode)&&(uint64_t)s.st_dev==d->device&&(uint64_t)s.st_ino==d->inode;}
static void destroy(void *context){struct delivery *d=context;if(d){if(identity(d))close(d->fd);free(d);}}
static void initialize(void){initialized=pthread_key_create(&key,destroy);}
static int ready(void){return !pthread_once(&once,initialize)&&!initialized;}
int xw_native_delivery_attach(int fd){
 if(!ready())return XW_MODE_FAULT;if(pthread_getspecific(key))return XW_MODE_BUSY;
 struct sockaddr_un peer;struct stat s;int kind;socklen_t size=sizeof kind;
 if(fd<3||delivery_getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&size)||size!=sizeof kind||kind!=SOCK_DGRAM)return XW_MODE_INVALID;
 size=sizeof peer;memset(&peer,0,sizeof peer);
 if(getpeername(fd,(struct sockaddr *)&peer,&size)||size<sizeof peer.sun_family||peer.sun_family!=AF_UNIX||fstat(fd,&s)||!S_ISSOCK(s.st_mode))return XW_MODE_INVALID;
 struct delivery *d=calloc(1,sizeof *d);if(!d)return XW_MODE_FAULT;
 d->fd=delivery_fcntl(fd,F_DUPFD,3);if(d->fd<0){free(d);return XW_MODE_FAULT;}
 d->device=s.st_dev;d->inode=s.st_ino;d->pid=getpid();d->thread=(unsigned long)pthread_self();
 if(delivery_fcntl(d->fd,F_SETFD,FD_CLOEXEC)<0||delivery_fcntl(d->fd,F_SETFL,O_NONBLOCK)<0||pthread_setspecific(key,d)){destroy(d);return XW_MODE_FAULT;}
 return 0;
}
int xw_native_delivery_attached(void){
 if(!ready())return 0;struct delivery *d=pthread_getspecific(key);
 return d&&!d->fault&&d->pid==(int)getpid()&&d->thread==(unsigned long)pthread_self()&&identity(d);
}
int xw_native_rf_refresh_offer(void){
 if(!ready())return XW_MODE_FAULT;struct delivery *d=pthread_getspecific(key);if(!d)return XW_MODE_PENDING;
 if(d->fault)return XW_MODE_FAULT;
 if(d->pid!=(int)getpid()||d->thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 if(!identity(d)){d->fault=1;return XW_MODE_FAULT;}
 return xw_native_offer_receive(d->fd);
}
int xw_native_delivery_send_notice(const unsigned char raw[64]){
 if(!raw||!ready())return XW_MODE_INVALID;struct delivery *d=pthread_getspecific(key);if(!d)return XW_MODE_DENIED;
 if(d->pid!=(int)getpid()||d->thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 if(d->fault||!identity(d))return XW_MODE_FAULT;
 ssize_t sent=delivery_send(d->fd,raw,64,MSG_DONTWAIT|MSG_NOSIGNAL);
 if(sent<0)return errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR?XW_MODE_PENDING:XW_MODE_FAULT;
 return sent==64?0:XW_MODE_FAULT;
}
int xw_native_rf_wait_offer(unsigned timeout){
 if(!timeout||timeout>200)return XW_MODE_INVALID;
 if(xw_native_rf_gui_owner())return XW_MODE_WRONG_OWNER;
 if(!ready())return XW_MODE_FAULT;struct delivery *d=pthread_getspecific(key);if(!d)return XW_MODE_PENDING;
 if(d->pid!=(int)getpid()||d->thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 struct hb_transfer_deadline deadline;if(hb_transfer_deadline_init(&deadline,timeout))return XW_MODE_FAULT;
 for(;;){
  if(d->fault||!identity(d)){d->fault=1;return XW_MODE_FAULT;}
  unsigned wait;int remaining=hb_transfer_deadline_remaining(&deadline,&wait);
  if(remaining!=1)return remaining==0?XW_MODE_PENDING:XW_MODE_FAULT;
  struct pollfd event={d->fd,POLLIN,0};int count=poll(&event,1,(int)wait);
  if(count<0){if(errno==EINTR)continue;return XW_MODE_FAULT;}
  if(!count)continue;
  if(event.revents&(POLLERR|POLLHUP|POLLNVAL))return XW_MODE_FAULT;
  int rc=xw_native_offer_receive(d->fd);if(rc!=XW_MODE_PENDING)return rc;
 }
}
