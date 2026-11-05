#define _DEFAULT_SOURCE
#include "native_offer.h"
#include "native_rf_worker.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/uio.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>
#include <errno.h>
extern unsigned long pthread_self(void);
extern int offer_fcntl(int,int,...) __asm__("fcntl");
extern int offer_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern ssize_t offer_sendmsg(int,const struct msghdr *,int) __asm__("sendmsg");
extern ssize_t offer_recvmsg(int,struct msghdr *,int) __asm__("recvmsg");
#ifdef __arm__
typedef char stock_offer_layout[(sizeof(struct msghdr)==28&&sizeof(struct cmsghdr)==12&&sizeof(struct iovec)==8)?1:-1];
#endif
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(i*8));}
static void put64(unsigned char *p,uint64_t n){for(unsigned i=0;i<8;i++)p[i]=(unsigned char)(n>>(i*8));}
static uint32_t get32(const unsigned char *p){uint32_t n=0;for(unsigned i=0;i<4;i++)n|=(uint32_t)p[i]<<(i*8);return n;}
static uint64_t get64(const unsigned char *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(i*8);return n;}
static int datagram(int fd){
 struct sockaddr_un peer;int kind=0;socklen_t size=sizeof kind;
 if(offer_getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&size)||size!=sizeof kind||kind!=SOCK_DGRAM)return 0;
 size=sizeof peer;memset(&peer,0,sizeof peer);
 return !getpeername(fd,(struct sockaddr *)&peer,&size)&&size>=sizeof peer.sun_family&&peer.sun_family==AF_UNIX;
}
static int transient(void){return errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR?XW_MODE_PENDING:XW_MODE_FAULT;}
static int peer_pid(int fd,int expected){
 struct {int pid;unsigned uid,gid;} credential;socklen_t size=sizeof credential;
 return expected>0&&!offer_getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&credential,&size)&&size==sizeof credential&&credential.pid==expected;
}
int xw_native_offer_send(struct xw_wireless_mode_policy *policy,int delivery,int observation,const struct xw_wireless_lease *lease){
 int rc=xw_mode_policy_data_allowed(policy,lease);if(rc)return rc;
 if(lease->mode!=XW_WIRELESS_MODE_WIFI||!datagram(delivery)||!datagram(observation))return XW_MODE_INVALID;
 unsigned char raw[64]={0};memcpy(raw,"WFO1",4);put32(raw+4,1);
 put64(raw+8,lease->generation);put64(raw+16,lease->serial);put64(raw+24,lease->consumer);
 put32(raw+32,lease->mode);put32(raw+36,getpid());put64(raw+40,pthread_self());
 union {struct cmsghdr alignment;unsigned char raw[CMSG_SPACE(sizeof(int))];} control;memset(&control,0,sizeof control);
 struct iovec vector={raw,sizeof raw};struct msghdr message;memset(&message,0,sizeof message);
 message.msg_iov=&vector;message.msg_iovlen=1;message.msg_control=control.raw;message.msg_controllen=sizeof control.raw;
 struct cmsghdr *header=CMSG_FIRSTHDR(&message);header->cmsg_level=SOL_SOCKET;header->cmsg_type=SCM_RIGHTS;header->cmsg_len=CMSG_LEN(sizeof(int));memcpy(CMSG_DATA(header),&observation,sizeof observation);
 ssize_t sent=offer_sendmsg(delivery,&message,MSG_DONTWAIT|MSG_NOSIGNAL);
 return sent<0?transient():sent==sizeof raw?0:XW_MODE_FAULT;
}
int xw_native_offer_receive(int delivery){
 if(!datagram(delivery))return XW_MODE_INVALID;
 unsigned char raw[64];union {struct cmsghdr alignment;unsigned char raw[CMSG_SPACE(8*sizeof(int))];} control;
 struct iovec vector={raw,sizeof raw};struct msghdr message;memset(&message,0,sizeof message);memset(&control,0,sizeof control);
 message.msg_iov=&vector;message.msg_iovlen=1;message.msg_control=control.raw;message.msg_controllen=sizeof control.raw;
 ssize_t received=offer_recvmsg(delivery,&message,MSG_DONTWAIT);if(received<0)return transient();
 int fds[8],count=0,bad=message.msg_flags&(MSG_TRUNC|MSG_CTRUNC);
 for(struct cmsghdr *h=CMSG_FIRSTHDR(&message);h;h=CMSG_NXTHDR(&message,h)){
  if(h->cmsg_level!=SOL_SOCKET||h->cmsg_type!=SCM_RIGHTS||h->cmsg_len<CMSG_LEN(0)){bad=1;continue;}
  size_t bytes=h->cmsg_len-CMSG_LEN(0);if(bytes%sizeof(int))bad=1;
  for(size_t i=0;i+sizeof(int)<=bytes;i+=sizeof(int)){int fd;memcpy(&fd,CMSG_DATA(h)+i,sizeof fd);if(count<8)fds[count++]=fd;else{close(fd);bad=1;}}
 }
 if(received!=sizeof raw||count!=1)bad=1;
 struct xw_wireless_lease lease={0};uint64_t gui_thread=0;int gui_pid=0;
 if(!bad){
  if(memcmp(raw,"WFO1",4)||get32(raw+4)!=1)bad=1;
  for(unsigned i=48;i<64;i++)if(raw[i])bad=1;
  lease.generation=get64(raw+8);lease.serial=get64(raw+16);lease.consumer=get64(raw+24);lease.mode=(int32_t)get32(raw+32);
  gui_pid=(int32_t)get32(raw+36);gui_thread=get64(raw+40);
  if(!lease.generation||!lease.serial||!lease.consumer||lease.mode!=XW_WIRELESS_MODE_WIFI||!peer_pid(delivery,gui_pid)||
     !gui_thread||gui_thread>ULONG_MAX||gui_thread==pthread_self()||!datagram(fds[0])||offer_fcntl(fds[0],F_SETFD,FD_CLOEXEC))bad=1;
 }
 int result=bad?XW_MODE_INVALID:xw_native_rf_worker_offer(fds[0],gui_pid,(unsigned long)gui_thread,&lease);
 for(int i=0;i<count;i++)close(fds[i]);return result;
}
