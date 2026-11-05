#include "../../runtime/platform/services/descriptor.h"
#include "../../runtime/platform/services/session.h"
#include <sys/socket.h>
#include <fcntl.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t fixture_sendmsg(int,const struct msghdr *,int) __asm__("sendmsg");
static unsigned open_count(void){unsigned n=0;for(int fd=0;fd<128;fd++)if(fixture_fcntl(fd,F_GETFD)>=0)n++;return n;}
int main(void){
 int channel[2],stream[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,channel)&&!socketpair(AF_UNIX,SOCK_STREAM,0,stream));
 struct xw_descriptor_offer offer={7,9,3},received,prior;memset(&received,0x5a,sizeof received);prior=received;int fd=-1;
 assert(xw_service_descriptor_receive(channel[1],&fd,&received)==XW_SESSION_BUSY&&fd==-1&&!memcmp(&received,&prior,sizeof prior));
 assert(!xw_service_descriptor_send(channel[0],stream[0],&offer));close(stream[0]);
 assert(!xw_service_descriptor_receive(channel[1],&fd,&received)&&received.generation==7&&received.session==9&&received.grants==3);
 assert(fixture_fcntl(fd,F_GETFD)&FD_CLOEXEC);assert(write(stream[1],"x",1)==1);char byte;assert(read(fd,&byte,1)==1&&byte=='x');
 close(fd);close(stream[1]);assert(send(channel[0],"bad",3,0)==3);fd=-1;prior=received;
 assert(xw_service_descriptor_receive(channel[1],&fd,&received)==XW_SESSION_INVALID&&fd==-1&&!memcmp(&prior,&received,sizeof prior));
 assert(!socketpair(AF_UNIX,SOCK_STREAM,0,stream));
 unsigned char data[32]={'X','F','D','1',3,0,0,0,7,0,0,0,0,0,0,0,9};
 union {struct cmsghdr alignment;unsigned char bytes[CMSG_SPACE(2*sizeof(int))];} extra;
 memset(&extra,0,sizeof extra);struct iovec vector={data,sizeof data};struct msghdr message;memset(&message,0,sizeof message);
 message.msg_iov=&vector;message.msg_iovlen=1;message.msg_control=extra.bytes;message.msg_controllen=sizeof extra.bytes;
 struct cmsghdr *header=CMSG_FIRSTHDR(&message);header->cmsg_level=SOL_SOCKET;header->cmsg_type=SCM_RIGHTS;header->cmsg_len=CMSG_LEN(2*sizeof(int));
 int two[2]={stream[0],stream[0]};memcpy(CMSG_DATA(header),two,sizeof two);
 assert(fixture_sendmsg(channel[0],&message,0)==32);unsigned before=open_count();
 assert(xw_service_descriptor_receive(channel[1],&fd,&received)==XW_SESSION_INVALID&&open_count()==before&&fd==-1);
 close(stream[0]);close(stream[1]);
 close(channel[0]);close(channel[1]);puts("Descriptor transfer: stock ABI, one connected stream, CLOEXEC, data flow and malformed refusal passed");return 0;
}
