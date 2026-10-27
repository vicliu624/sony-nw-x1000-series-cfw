#define _GNU_SOURCE
#include "connect_step.h"
#include <fcntl.h>
#include <poll.h>
#include <unistd.h>
#include <errno.h>
#include <netinet/in.h>
#include <sys/un.h>
/* Modern time64 redirects also cover non-time options. Bind only these
 * scalar calls explicitly; never pass modern flock/timeval structures. */
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern int sony_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
typedef char hb_socklen_must_be_32[(sizeof(socklen_t)==4&&sizeof(int)==4)?1:-1];
static int fail(struct hb_connect *c,int error){
 c->system_error=error==HB_CONNECT_IO?errno:0;
 if(c->fd>=0){if(close(c->fd)){error=HB_CONNECT_IO;c->system_error=errno;}c->fd=-1;}
 c->state=HB_CONNECT_FAILED;return error;
}
static int budget(struct hb_connect *c,unsigned *wait){
 if(c->stop&&*c->stop)return HB_CONNECT_CANCELLED;
 int result=hb_transfer_deadline_remaining(c->deadline,wait);
 return result<0?HB_CONNECT_CLOCK:result?0:HB_CONNECT_DEADLINE;
}
void hb_connect_init(struct hb_connect *c){if(c){c->fd=-1;c->system_error=0;c->state=HB_CONNECT_EMPTY;c->deadline=0;c->stop=0;}}
int hb_connect_begin(struct hb_connect *c,int family,const struct sockaddr *address,socklen_t length,struct hb_transfer_deadline *deadline,volatile int *stop){
 if(!c||c->state!=HB_CONNECT_EMPTY||!address||length<sizeof address->sa_family||address->sa_family!=family||!deadline||
    (family!=AF_UNIX&&family!=AF_INET&&family!=AF_INET6))return HB_CONNECT_INPUT;
 if((family==AF_INET&&length!=sizeof(struct sockaddr_in))||(family==AF_INET6&&length!=sizeof(struct sockaddr_in6))||
    (family==AF_UNIX&&(length>sizeof(struct sockaddr_un)||length<sizeof address->sa_family+1)))return HB_CONNECT_INPUT;
 c->deadline=deadline;c->stop=stop;unsigned wait;int result=budget(c,&wait);if(result)return fail(c,result);
 c->fd=socket(family,SOCK_STREAM,0);if(c->fd<0)return fail(c,HB_CONNECT_IO);
 int flags=sony_fcntl(c->fd,F_GETFL,0);if(flags<0||sony_fcntl(c->fd,F_SETFL,flags|O_NONBLOCK))return fail(c,HB_CONNECT_IO);
 result=connect(c->fd,address,length);
 if(!result){result=budget(c,&wait);if(result)return fail(c,result);c->state=HB_CONNECT_READY;return 1;}
 if(errno!=EINPROGRESS&&errno!=EALREADY)return fail(c,stop&&*stop?HB_CONNECT_CANCELLED:HB_CONNECT_IO);
 c->state=HB_CONNECT_PENDING;return 0;
}
int hb_connect_step(struct hb_connect *c,unsigned cap){
 if(!c||cap>1000||c->state!=HB_CONNECT_PENDING)return HB_CONNECT_INPUT;
 unsigned wait;int result=budget(c,&wait);if(result)return fail(c,result);if(wait>cap)wait=cap;
 struct pollfd p={c->fd,POLLOUT,0};result=poll(&p,1,(int)wait);
 if(c->stop&&*c->stop)return fail(c,HB_CONNECT_CANCELLED);
 if(result<0){if(errno==EINTR)return 0;return fail(c,HB_CONNECT_IO);}
 int timed=budget(c,&wait);if(timed)return fail(c,timed);
 if(!result)return 0;
 if(p.revents&POLLNVAL)return fail(c,HB_CONNECT_IO);
 if(!(p.revents&(POLLOUT|POLLERR|POLLHUP)))return 0;
 int error=0;socklen_t size=sizeof error;
 if(sony_getsockopt(c->fd,SOL_SOCKET,SO_ERROR,&error,&size)||size!=sizeof error)return fail(c,HB_CONNECT_IO);
 if(error){errno=error;return fail(c,HB_CONNECT_IO);}
 result=budget(c,&wait);if(result)return fail(c,result);
 c->state=HB_CONNECT_READY;return 1;
}
int hb_connect_take(struct hb_connect *c){
 if(!c||c->state!=HB_CONNECT_READY||c->fd<0)return -1;
 int fd=c->fd;c->fd=-1;c->state=HB_CONNECT_TAKEN;return fd;
}
int hb_connect_release(struct hb_connect *c){
 if(!c)return HB_CONNECT_INPUT;
 int result=0;if(c->fd>=0){if(close(c->fd))result=HB_CONNECT_IO;c->fd=-1;}
 if(c->state!=HB_CONNECT_TAKEN)c->state=HB_CONNECT_EMPTY;
 return result;
}
