/* ARM-only test boundary, no real socket/ioctl or driver device. */
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <assert.h>
#include <sys/socket.h>
#include <linux/wireless.h>
#include "radio_inspect_mock.h"
extern FILE *__real_fopen(const char *,const char *);
extern int __real_close(int);
FILE *__wrap_fopen(const char *p,const char *m){assert(!strcmp(p,"/proc/net/wlan/info")&&!strcmp(m,"r"));return __real_fopen(INSPECT_DRIVER_INFO,m);}
FILE *__wrap_fopen64(const char *p,const char *m){return __wrap_fopen(p,m);}
int __wrap_socket(int domain,int type,int protocol){assert(domain==AF_INET&&type==SOCK_DGRAM&&!protocol);return 96;}
int __wrap_close(int fd){return fd==96?0:__real_close(fd);}
int __wrap_ioctl(int fd,unsigned long op,...){
 va_list ap;va_start(ap,op);struct iwreq *r=va_arg(ap,struct iwreq *);va_end(ap);assert(fd==96&&op==0x8be4&&sizeof(*r)==32&&!strcmp(r->ifr_name,"eth0")&&r->u.data.length==20);
 uint8_t *p=r->u.data.pointer;assert(p[0]==0x86&&!p[1]&&p[2]==20&&!p[3]&&!p[8]&&!p[9]&&!p[10]&&!p[11]);
 uint32_t address=0;for(unsigned i=0;i<4;i++)address|=(uint32_t)p[12+i]<<(i*8);
 unsigned at=0;for(;at<sizeof(mock_words)/sizeof(mock_words[0]);at++)if(mock_words[at][0]==address)break;assert(at<sizeof(mock_words)/sizeof(mock_words[0]));uint32_t value=mock_words[at][1];
 p[1]=0x80;p[6]=p[7]=0;for(unsigned i=0;i<4;i++)p[16+i]=(uint8_t)(value>>(i*8));return 0;
}
