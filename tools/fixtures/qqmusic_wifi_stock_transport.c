/* PC/QEMU fixture only: retain original cnmgr bytes and real FIFO/lockf IO.
 * Redirect its fixed FIFO paths to one private test directory. No WLAN/QQ. */
#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
static int redirect(const char *path,char out[1024]){
 const char *root=getenv("QQ_TEST_FIFO_ROOT");size_t a,b;
 if(!root||!path||strncmp(path,"/tmp/cnmgr_",11)){errno=EACCES;return -1;}
 a=strlen(root);b=strlen(path+5);if(!a||a+b+2>1024){errno=ENAMETOOLONG;return -1;}
 memcpy(out,root,a);out[a]='/';memcpy(out+a+1,path+5,b+1);return 0;
}
int fixture_open(const char *,int,...) __asm__("open");
int fixture_open(const char *path,int flags,...){
 char target[1024];mode_t mode=0;va_list ap;
 if(flags&O_CREAT){va_start(ap,flags);mode=(mode_t)va_arg(ap,int);va_end(ap);}
 if(redirect(path,target))return -1;
 return (int)syscall(SYS_open,target,flags,mode);
}
int mkfifo(const char *path,mode_t mode){char target[1024];if(redirect(path,target))return -1;return (int)syscall(SYS_mknod,target,S_IFIFO|mode,0);}
int connect(int fd,const struct sockaddr *address,socklen_t bytes){(void)fd;(void)address;(void)bytes;errno=ENOENT;return -1;}
int qq_wifi_ipc_guard(void){return getenv("QQ_TEST_FIFO_ROOT")?0:-1;}
int qq_wifi_route_ready(void){return 1;} /* Kernel route boundary is synthetic. */
