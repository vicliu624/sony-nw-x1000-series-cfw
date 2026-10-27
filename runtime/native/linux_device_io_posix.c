/* libc I/O for the verified non-time X1000 display/touch request set. */
#include "linux_device_io.h"
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <poll.h>
#include <sys/mman.h>
#include <unistd.h>
/* Stock ioctl was verified as a direct r0/r1/r2 OABI wrapper. Do not alias
 * modern __ioctl_time64; no time-bearing requests are accepted here. */
extern int hb_stock_device_ioctl(int,unsigned long,void *) __asm__("ioctl");
typedef char poll_layout[(sizeof(struct hb_device_pollfd)==sizeof(struct pollfd)&&offsetof(struct hb_device_pollfd,revents)==offsetof(struct pollfd,revents))?1:-1];
static long result(long n){return n<0?-errno:n;}
long hb_device_io_open(const char *path,int flags){if(flags!=O_RDONLY&&flags!=O_RDWR)return -EINVAL;return result(open(path,flags,0));}
long hb_device_io_close(int fd){return result(close(fd));}
long hb_device_io_ioctl(int fd,unsigned command,void *value){
 switch(command){
 case 0x4602:case 0x4600:case 0x80044e04:case 0x5404:
 case 0x80044e00:case 0x40044e01:case 0x80045401:break;
 default:return -EINVAL;
 }
 return result(hb_stock_device_ioctl(fd,command,value));
}
long hb_device_io_map(unsigned bytes,int fd){
 void *p=mmap(0,bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
 return p==MAP_FAILED?-errno:(long)p;
}
long hb_device_io_unmap(void *p,unsigned bytes){return result(munmap(p,bytes));}
long hb_device_io_poll(struct hb_device_pollfd *p,int timeout){return result(poll((struct pollfd *)p,1,timeout));}

