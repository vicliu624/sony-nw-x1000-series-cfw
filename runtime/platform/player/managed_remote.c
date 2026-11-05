#include "managed_remote.h"
#include <sys/socket.h>
#include <poll.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
extern int remote_fcntl(int,int,...) __asm__("fcntl");
static uint32_t u32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
int xw_managed_remote_adopt(struct xw_managed_remote *r,int fd,unsigned timeout,volatile int *stop,void *context,int (*clock)(void *,uint64_t *)){
 if(!r||r->bound||fd<0||!clock||!timeout||timeout>5000)return XW_PLAYER_INVALID;
 if(remote_fcntl(fd,F_SETFD,FD_CLOEXEC))return XW_PLAYER_IO;
 memset(r,0,sizeof *r);r->fd=fd;r->bound=1;r->timeout=timeout;r->stop=stop;r->clock=clock;r->clock_context=context;return 0;
}
static int wait_io(struct xw_managed_remote *r,short events,uint64_t end,uint64_t *last){
 if(r->stop&&*r->stop)return XW_PLAYER_UNAVAILABLE;
 uint64_t now;if(r->clock(r->clock_context,&now)||now<*last)return XW_PLAYER_IO;*last=now;
 if(now>=end)return XW_PLAYER_UNAVAILABLE;
 int delay=end-now>100?100:(int)(end-now);struct pollfd p={r->fd,events,0};int rc=poll(&p,1,delay);
 if(rc<0)return errno==EINTR?XW_PLAYER_BUSY:XW_PLAYER_IO;
 if(!rc)return XW_PLAYER_BUSY;
 if(p.revents&(POLLERR|POLLNVAL))return XW_PLAYER_IO;
 return p.revents&(events|POLLHUP)?0:XW_PLAYER_BUSY;
}
int xw_managed_remote_exchange(struct xw_managed_remote *r,const unsigned char *input,size_t bytes){
 if(!r||!r->bound)return XW_PLAYER_CLOSED;if(r->busy)return XW_PLAYER_BUSY;
 if(!input||bytes<20||bytes>XW_RPC_REQUEST_MAX)return XW_PLAYER_INVALID;
 uintptr_t in=(uintptr_t)input,scratch=(uintptr_t)r->reply;
 if(in>=scratch?in-scratch<sizeof r->reply:scratch-in<bytes)return XW_PLAYER_INVALID;
 int control=!memcmp(input,"XLC1",4),command=0;uint32_t kind=0,serial=0;
 if(control){
  if(bytes!=40)return XW_PLAYER_INVALID;unsigned char check[40];uint64_t correlation=(uint64_t)u32(input+8)|(uint64_t)u32(input+12)<<32,generation=(uint64_t)u32(input+16)|(uint64_t)u32(input+20)<<32,after=(uint64_t)u32(input+24)|(uint64_t)u32(input+28)<<32;
  if(xw_control_request_encode(u32(input+4),correlation,generation,after,u32(input+32),check,sizeof check)||memcmp(check,input,40))return XW_PLAYER_INVALID;
 }else{struct xw_rpc_request request;int rc=xw_rpc_decode_request(input,bytes,&request);if(rc)return rc;kind=request.kind;serial=request.serial;command=kind==XW_RPC_COMMAND;}
 r->busy=1;r->reply_bytes=0;uint64_t last,end;int rc=XW_PLAYER_IO;size_t sent=0,received=0,expected=control?24:20;
 if(r->clock(r->clock_context,&last)||last>UINT64_MAX-r->timeout)goto done;end=last+r->timeout;
 while(sent<bytes){
  rc=wait_io(r,POLLOUT,end,&last);if(rc==XW_PLAYER_BUSY)continue;if(rc)goto done;
  ssize_t n=send(r->fd,input+sent,bytes-sent,MSG_DONTWAIT|MSG_NOSIGNAL);if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR))continue;if(n<=0){rc=XW_PLAYER_IO;goto done;}sent+=(size_t)n;
 }
 while(received<expected){
  rc=wait_io(r,POLLIN,end,&last);if(rc==XW_PLAYER_BUSY)continue;if(rc)goto done;
  ssize_t n=recv(r->fd,r->reply+received,expected-received,MSG_DONTWAIT);if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR))continue;if(n<=0){rc=XW_PLAYER_IO;goto done;}received+=(size_t)n;
  if(control&&received==24&&expected==24){
   if(memcmp(r->reply,"XLR1",4)||memcmp(r->reply+4,input+4,12)||u32(r->reply+20)>sizeof r->reply-24){rc=XW_PLAYER_PROTOCOL;goto done;}expected=24+u32(r->reply+20);
  }else if(!control&&received==20&&expected==20){
   unsigned reply;uint32_t k,s,body;if(xw_rpc_header(r->reply,&reply,&k,&s,&body)||!reply||k!=kind||s!=serial||body<4){rc=XW_PLAYER_PROTOCOL;goto done;}expected=20+body;
  }
 }
 rc=0;r->reply_bytes=received;
done:
 r->busy=0;if(rc){close(r->fd);r->fd=-1;r->bound=0;return command&&sent?XW_PLAYER_UNCERTAIN:rc;}return 0;
}
int xw_managed_remote_detach(struct xw_managed_remote *r){
 if(!r||!r->bound)return XW_PLAYER_CLOSED;if(r->busy)return XW_PLAYER_BUSY;
 close(r->fd);r->fd=-1;r->bound=0;r->reply_bytes=0;return 0;
}
