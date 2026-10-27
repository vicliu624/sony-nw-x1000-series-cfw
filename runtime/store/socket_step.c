#define _GNU_SOURCE
#include "socket_step.h"
#include <sys/socket.h>
#include <poll.h>
#include <errno.h>
typedef char hb_pollfd_layout_must_be_8[(sizeof(struct pollfd)==8)?1:-1];
static int step(int fd,unsigned char *out,const unsigned char *input,unsigned bytes,unsigned timeout,volatile int *stop){
 if(fd<0||!bytes||bytes>65536u||timeout>1000u||(!out&&!input))return HB_SOCKET_ERROR;
 if(stop&&*stop)return HB_SOCKET_CANCELLED;
 struct pollfd p={fd,(short)(out?POLLIN:POLLOUT),0};
 int ready=poll(&p,1,(int)timeout);
 if(stop&&*stop)return HB_SOCKET_CANCELLED;
 if(ready<0)return errno==EINTR?HB_SOCKET_RETRY:HB_SOCKET_ERROR;
 if(!ready)return HB_SOCKET_TIMEOUT;
 if(p.revents&POLLNVAL)return HB_SOCKET_ERROR;
 if(!(p.revents&(p.events|POLLHUP|POLLERR)))return HB_SOCKET_RETRY;
 ssize_t n=out?recv(fd,out,bytes,MSG_DONTWAIT):send(fd,input,bytes,MSG_DONTWAIT|MSG_NOSIGNAL);
 if(n<0){
  if(stop&&*stop)return HB_SOCKET_CANCELLED;
  return errno==EINTR||errno==EAGAIN||errno==EWOULDBLOCK?HB_SOCKET_RETRY:HB_SOCKET_ERROR;
 }
 if(!out&&!n)return HB_SOCKET_ERROR;
 return (int)n;
}
int hb_socket_read_step(int fd,unsigned char *out,unsigned capacity,unsigned timeout,volatile int *stop){
 if(!out)return HB_SOCKET_ERROR;
 return step(fd,out,0,capacity,timeout,stop);
}
int hb_socket_write_step(int fd,const unsigned char *input,unsigned bytes,unsigned timeout,volatile int *stop){
 if(!input)return HB_SOCKET_ERROR;
 return step(fd,0,input,bytes,timeout,stop);
}
