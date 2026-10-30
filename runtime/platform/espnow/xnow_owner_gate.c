#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_owner_gate.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int gate_fcntl(int,int,...) __asm__("fcntl");
#ifndef XNOW_OWNER_GATE_NAMESPACE
#define XNOW_OWNER_GATE_NAMESPACE "x1000-xnow-chat-owner-v1"
#endif
static const char name[]=XNOW_OWNER_GATE_NAMESPACE;
static void empty(struct xnow_owner_gate *g){memset(g,0,sizeof(*g));g->socket_fd=g->command_fd=-1;}
int xnow_owner_gate_open(struct xnow_owner_gate *g,int input,const volatile int *stop,void *context,int (*storage)(void *)){
 if(!g||input<0||!stop||!storage||sizeof(name)<2||sizeof(name)>sizeof(((struct sockaddr_un *)0)->sun_path))return XNOW_ARGUMENT;
 empty(g);g->pid=(int)getpid();g->stop_token=stop;g->storage_context=context;g->storage_guard=storage;
 struct stat st;int flags=gate_fcntl(input,F_GETFL);
 if(flags<0||(flags&O_ACCMODE)!=O_RDONLY||fstat(input,&st)||!S_ISFIFO(st.st_mode)||*stop)return XNOW_IDENTITY;
 g->command_device=(uint64_t)st.st_dev;g->command_inode=(uint64_t)st.st_ino;
 g->command_fd=gate_fcntl(input,F_DUPFD,3);if(g->command_fd<0)return XNOW_IO;
 if(gate_fcntl(g->command_fd,F_SETFD,FD_CLOEXEC)<0||fstat(g->command_fd,&st)||(uint64_t)st.st_dev!=g->command_device||(uint64_t)st.st_ino!=g->command_inode)goto failed;
 g->socket_fd=socket(AF_UNIX,SOCK_DGRAM,0);if(g->socket_fd<0)goto failed;
 struct sockaddr_un address;memset(&address,0,sizeof(address));address.sun_family=AF_UNIX;memcpy(address.sun_path+1,name,sizeof(name)-1);
 socklen_t n=(socklen_t)(sizeof(address.sun_family)+sizeof(name));
 if(bind(g->socket_fd,(struct sockaddr *)&address,n)||gate_fcntl(g->socket_fd,F_SETFD,FD_CLOEXEC)<0||fstat(g->socket_fd,&st)||!S_ISSOCK(st.st_mode))goto failed;
 g->socket_device=(uint64_t)st.st_dev;g->socket_inode=(uint64_t)st.st_ino;return 0;
failed:
 if(g->socket_fd>=0)close(g->socket_fd);
 if(g->command_fd>=0)close(g->command_fd);
 empty(g);return XNOW_IDENTITY;
}
int xnow_owner_gate_radio_valid(void *context){
 struct xnow_owner_gate *g=context;if(!g||g->radio_fault||g->pid!=(int)getpid()||g->socket_fd<0)return 0;
 struct stat st;struct sockaddr_un address;socklen_t n=sizeof(address);memset(&address,0,sizeof(address));
 if(fstat(g->socket_fd,&st)||!S_ISSOCK(st.st_mode)||(uint64_t)st.st_dev!=g->socket_device||(uint64_t)st.st_ino!=g->socket_inode||getsockname(g->socket_fd,(struct sockaddr *)&address,&n)||n!=sizeof(address.sun_family)+sizeof(name)||address.sun_family!=AF_UNIX||address.sun_path[0]||memcmp(address.sun_path+1,name,sizeof(name)-1)){g->radio_fault=1;g->stopping=g->data_revoked=1;return 0;}
 return 1;
}
int xnow_owner_gate_stop_requested(struct xnow_owner_gate *g){
 if(!g||g->pid!=(int)getpid())return 1;
 if(!xnow_owner_gate_radio_valid(g))return 1;
 if(g->stop_token&&*g->stop_token)g->stopping=g->data_revoked=1;
 if(!g->stopping){struct stat st;
  if(g->command_fd<0||fstat(g->command_fd,&st)||!S_ISFIFO(st.st_mode)||(uint64_t)st.st_dev!=g->command_device||(uint64_t)st.st_ino!=g->command_inode){g->stopping=g->data_revoked=1;return 1;}
  struct pollfd p={g->command_fd,POLLIN|POLLHUP|POLLERR,0};int result=poll(&p,1,0);
  if((result<0&&errno!=EINTR)||(result>0&&(p.revents&(POLLHUP|POLLERR|POLLNVAL))))g->stopping=g->data_revoked=1;
 }
 return g->stopping;
}
int xnow_owner_gate_storage_guard(void *context){
 struct xnow_owner_gate *g=context;if(!g||xnow_owner_gate_stop_requested(g)||g->data_revoked)return -1;
 if(g->storage_guard(g->storage_context)){g->stopping=g->data_revoked=1;return -1;}
 return 0;
}
int xnow_owner_gate_step(struct xnow_owner_gate *g,struct xnow_full_control *controller){
 if(!g||!controller||g->pid!=(int)getpid())return XNOW_ARGUMENT;
 if(xnow_owner_gate_stop_requested(g))xnow_full_control_stop(controller);
 return xnow_full_control_step(controller);
}
int xnow_owner_gate_release(struct xnow_owner_gate *g,const struct xnow_full_control *controller){
 if(!g||g->pid!=(int)getpid()||!controller||!xnow_full_control_finished(controller))return XNOW_UNCERTAIN;
 int result=0;struct stat st;
 if(g->command_fd>=0){if(fstat(g->command_fd,&st)||!S_ISFIFO(st.st_mode)||(uint64_t)st.st_dev!=g->command_device||(uint64_t)st.st_ino!=g->command_inode)result=XNOW_UNCERTAIN;else if(close(g->command_fd))result=XNOW_UNCERTAIN;}
 if(g->socket_fd>=0){if(fstat(g->socket_fd,&st)||!S_ISSOCK(st.st_mode)||(uint64_t)st.st_dev!=g->socket_device||(uint64_t)st.st_ino!=g->socket_inode)result=XNOW_UNCERTAIN;else if(close(g->socket_fd))result=XNOW_UNCERTAIN;}
 empty(g);return result;
}
