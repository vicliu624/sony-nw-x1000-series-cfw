/* Owner-only notifier kept separate from lightweight foreground pipe logic. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_handoff.h"
#include "xnow_full_control.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int handoff_fcntl(int,int,...) __asm__("fcntl");
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
int xnow_handoff_notify(int fd,const uint8_t cookie[16],const struct xnow_full_control *controller){
 if(fd<0||!cookie||!controller)return XNOW_ARGUMENT;
 unsigned any=0;for(unsigned i=0;i<16;i++)any|=cookie[i];if(!any)return XNOW_ARGUMENT;
 if(!xnow_full_control_finished(controller))return XNOW_PENDING;
 struct stat s;int mode=handoff_fcntl(fd,F_GETFL);if(mode<0||(mode&O_ACCMODE)!=O_WRONLY||fstat(fd,&s)||!S_ISFIFO(s.st_mode))return XNOW_IDENTITY;
 uint8_t record[32];memcpy(record,"XRFDONE1",8);memcpy(record+8,cookie,16);put32(record+24,1);put32(record+28,(uint32_t)controller->session.failure);
 ssize_t n;do{n=write(fd,record,sizeof(record));}while(n<0&&errno==EINTR);
 if(n<0&&errno==EAGAIN)return XNOW_PENDING;
 return n==32?0:XNOW_UNCERTAIN;
}
