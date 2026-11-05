#include "startup_delivery.h"
#include "../../store/deadline.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
extern int startup_fcntl(int,int,...) __asm__("fcntl");
static int address(struct sockaddr_un *out,const char *directory,const char *leaf){
 static const char prefix[]="/tmp/x1000-player-";
 if(!directory||strncmp(directory,prefix,sizeof prefix-1))return -1;
 const char *p=directory+sizeof prefix-1;if(!*p)return -1;
 for(;*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='-'))return -1;
 size_t a=strlen(directory),b=strlen(leaf);
 if(a+b+2>sizeof out->sun_path)return -1;
 memset(out,0,sizeof *out);out->sun_family=AF_UNIX;
 memcpy(out->sun_path,directory,a);out->sun_path[a]='/';memcpy(out->sun_path+a+1,leaf,b+1);return 0;
}
static int packet(unsigned char out[64],const char *magic,const char *nonce,uint64_t generation,uint32_t grants){
 if(!nonce||strlen(nonce)!=32||!generation||!grants||(grants&~7u))return -1;
 for(unsigned i=0;i<32;i++)if(!((nonce[i]>='0'&&nonce[i]<='9')||(nonce[i]>='a'&&nonce[i]<='f')))return -1;
 memset(out,0,64);memcpy(out,magic,4);out[4]=(unsigned char)grants;
 for(unsigned i=0;i<8;i++)out[8+i]=(unsigned char)(generation>>(8*i));
 memcpy(out+16,nonce,32);return 0;
}
static int endpoint(const struct sockaddr_un *a){
 int fd=socket(AF_UNIX,SOCK_DGRAM,0);if(fd<0)return -1;
 if(startup_fcntl(fd,F_SETFD,FD_CLOEXEC)||bind(fd,(const struct sockaddr *)a,sizeof *a)){close(fd);return -1;}
 return fd;
}
int xw_player_startup_listen(const char *directory){
 struct sockaddr_un a;if(address(&a,directory,"controller.sock"))return -1;
 return endpoint(&a); /* Never unlink a pre-existing endpoint. */
}
int xw_player_startup_accept(int fd,const char *directory,const char *nonce,uint64_t generation,uint32_t grants){
 struct sockaddr_un expected,peer;socklen_t size=sizeof peer;
 unsigned char want[64],data[65];
 if(fd<0||address(&expected,directory,"player.sock")||packet(want,"XIS1",nonce,generation,grants))return -1;
 memset(&peer,0,sizeof peer);
 ssize_t n=recvfrom(fd,data,sizeof data,MSG_DONTWAIT,(struct sockaddr *)&peer,&size);
 if(n<0)return errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR?1:-1;
 if(n!=64||memcmp(data,want,64)||size>sizeof peer||peer.sun_family!=AF_UNIX||memcmp(peer.sun_path,expected.sun_path,sizeof peer.sun_path))return -1;
 if(connect(fd,(struct sockaddr *)&expected,sizeof expected))return -1;
 memcpy(want,"XIA1",4);
 return send(fd,want,sizeof want,MSG_DONTWAIT|MSG_NOSIGNAL)==sizeof want?0:-1;
}
int xw_player_startup_connect(const char *directory,const char *nonce,uint64_t generation,uint32_t grants,unsigned timeout_ms){
 struct sockaddr_un local,remote;unsigned char hello[64],reply[65];
 if(!timeout_ms||timeout_ms>3000||address(&local,directory,"player.sock")||address(&remote,directory,"controller.sock")||packet(hello,"XIS1",nonce,generation,grants))return -1;
 int fd=endpoint(&local);if(fd<0)return -1;
 if(connect(fd,(struct sockaddr *)&remote,sizeof remote)||send(fd,hello,sizeof hello,MSG_DONTWAIT|MSG_NOSIGNAL)!=sizeof hello)goto failed;
 unsigned long long last,end;if(hb_monotonic_millis(&last)||last>UINT64_MAX-timeout_ms)goto failed;end=last+timeout_ms;
 for(;;){
  unsigned long long now;if(hb_monotonic_millis(&now)||now<last||now>=end)goto failed;last=now;
  unsigned wait=end-now>100?100:(unsigned)(end-now);
  struct pollfd p={fd,POLLIN,0};int ready=poll(&p,1,(int)wait);
  if(ready<0&&errno==EINTR)continue;
  if(ready<0||p.revents&(POLLERR|POLLNVAL|POLLHUP))goto failed;
  if(!ready)continue;
  ssize_t n=recv(fd,reply,sizeof reply,MSG_DONTWAIT);
  if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR))continue;
  memcpy(hello,"XIA1",4);if(n!=64||memcmp(reply,hello,64))goto failed;
  unlink(local.sun_path);return fd;
 }
failed:
 close(fd);unlink(local.sun_path);return -1;
}
