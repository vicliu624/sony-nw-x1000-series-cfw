#include "descriptor.h"
#include "session.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/uio.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
extern ssize_t transfer_sendmsg(int,const struct msghdr *,int) __asm__("sendmsg");
extern ssize_t transfer_recvmsg(int,struct msghdr *,int) __asm__("recvmsg");
extern int transfer_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern int transfer_fcntl(int,int,...) __asm__("fcntl");
#ifdef __arm__
typedef char stock_message_layout[(sizeof(struct msghdr)==28&&sizeof(struct cmsghdr)==12&&sizeof(struct iovec)==8&&sizeof(socklen_t)==4)?1:-1];
#endif
static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
static uint32_t u32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int socket_kind(int fd,int expected){
 struct sockaddr_un peer; socklen_t size=sizeof peer;int kind=0;
 if(getpeername(fd,(struct sockaddr *)&peer,&size)||size<sizeof(peer.sun_family)||peer.sun_family!=AF_UNIX)return 0;
 size=sizeof kind;return !transfer_getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&size)&&size==sizeof kind&&kind==expected;
}
static int io_result(void){return errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR?XW_SESSION_BUSY:XW_SESSION_FAULT;}
int xw_service_descriptor_send(int channel,int connection,const struct xw_descriptor_offer *offer){
 if(!offer||!offer->generation||!offer->session||!offer->grants||!socket_kind(channel,SOCK_DGRAM)||!socket_kind(connection,SOCK_STREAM))return XW_SESSION_INVALID;
 unsigned char data[32]={0};memcpy(data,"XFD1",4);put32(data+4,offer->grants);put32(data+8,(uint32_t)offer->generation);put32(data+12,(uint32_t)(offer->generation>>32));put32(data+16,(uint32_t)offer->session);put32(data+20,(uint32_t)(offer->session>>32));
 union {struct cmsghdr alignment;unsigned char bytes[CMSG_SPACE(sizeof(int))];} control;memset(&control,0,sizeof control);
 struct iovec vector={data,sizeof data};struct msghdr message;memset(&message,0,sizeof message);message.msg_iov=&vector;message.msg_iovlen=1;message.msg_control=control.bytes;message.msg_controllen=sizeof control.bytes;
 struct cmsghdr *header=CMSG_FIRSTHDR(&message);header->cmsg_level=SOL_SOCKET;header->cmsg_type=SCM_RIGHTS;header->cmsg_len=CMSG_LEN(sizeof(int));memcpy(CMSG_DATA(header),&connection,sizeof connection);
 ssize_t n=transfer_sendmsg(channel,&message,MSG_DONTWAIT|MSG_NOSIGNAL);return n<0?io_result():n==sizeof data?0:XW_SESSION_FAULT;
}
int xw_service_descriptor_receive(int channel,int *connection,struct xw_descriptor_offer *out){
 if(!connection||!out||!socket_kind(channel,SOCK_DGRAM))return XW_SESSION_INVALID;
 unsigned char data[32];union {struct cmsghdr alignment;unsigned char bytes[CMSG_SPACE(8*sizeof(int))];} control;
 struct iovec vector={data,sizeof data};struct msghdr message;memset(&message,0,sizeof message);memset(&control,0,sizeof control);message.msg_iov=&vector;message.msg_iovlen=1;message.msg_control=control.bytes;message.msg_controllen=sizeof control.bytes;
 ssize_t n=transfer_recvmsg(channel,&message,MSG_DONTWAIT);if(n<0)return io_result();
 int descriptors[8],count=0,bad=message.msg_flags&(MSG_TRUNC|MSG_CTRUNC);
 for(struct cmsghdr *h=CMSG_FIRSTHDR(&message);h;h=CMSG_NXTHDR(&message,h)){
  if(h->cmsg_level!=SOL_SOCKET||h->cmsg_type!=SCM_RIGHTS||h->cmsg_len<CMSG_LEN(0)){bad=1;continue;}
  size_t bytes=h->cmsg_len-CMSG_LEN(0);if(bytes%sizeof(int))bad=1;
  for(size_t i=0;i+sizeof(int)<=bytes;i+=sizeof(int)){int fd;memcpy(&fd,CMSG_DATA(h)+i,sizeof fd);if(count<8)descriptors[count++]=fd;else{close(fd);bad=1;}}
 }
 if(n!=sizeof data||count!=1||memcmp(data,"XFD1",4)||u32(data+24)||u32(data+28))bad=1;
 struct xw_descriptor_offer offer={0};if(!bad){offer.grants=u32(data+4);offer.generation=u32(data+8)|(uint64_t)u32(data+12)<<32;offer.session=u32(data+16)|(uint64_t)u32(data+20)<<32;
  if(!offer.grants||!offer.generation||!offer.session||!socket_kind(descriptors[0],SOCK_STREAM)||transfer_fcntl(descriptors[0],F_SETFD,FD_CLOEXEC))bad=1;
 }
 if(bad){for(int i=0;i<count;i++)close(descriptors[i]);return XW_SESSION_INVALID;}
 *connection=descriptors[0];*out=offer;return 0;
}
