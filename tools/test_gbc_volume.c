#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static unsigned code,value,available;
int open(const char*p,int flags,...){assert(!strcmp(p,"/dev/input/event0")&&flags==(O_RDONLY|O_NONBLOCK));return 77;}
int volume_fcntl(int,int,...) __asm__("fcntl");
int volume_fcntl(int fd,int command,...){assert(fd==77&&command==F_SETFD);return 0;}
int close(int fd){assert(fd==77);return 0;}
ssize_t read(int fd,void*p,size_t n){assert(fd==77&&n>=16);if(!available){errno=EAGAIN;return -1;}unsigned char*b=p;memset(b,0,16);b[8]=1;b[10]=code;b[12]=value;available=0;return 16;}
int hb_stop_signals_install(volatile int*p){*p=0;return 0;}
int hb_devices_open(struct hb_devices*d,const unsigned short*p,unsigned n,volatile int*s){(void)p;assert(n==240*432);memset(d,0,sizeof(*d));d->stop=s;return 0;}
int hb_devices_close(struct hb_devices*d){(void)d;return 0;}
void hb_devices_present(struct hb_devices*d){(void)d;}
int hb_devices_next_touch(struct hb_devices*d,unsigned char p[11],int ms){(void)d;(void)p;assert(!ms);return 0;}
static void emit(struct ep*p,unsigned c,unsigned v){code=c;value=v;available=1;assert(!ep_poll(p,0));}
int main(void){struct ep p;assert(!ep_open(&p));emit(&p,17,1);assert(p.volume_delta==5&&!p.buttons);emit(&p,17,0);assert(!p.volume_delta&&!p.buttons);emit(&p,16,1);assert(p.volume_delta==-5&&!p.buttons);emit(&p,16,2);assert(p.volume_delta==-5&&!p.buttons);emit(&p,0,1);assert(p.buttons==EP_A&&!p.volume_delta);emit(&p,18,1);assert(p.exit);assert(!ep_close(&p));puts("GBC physical volume +/- and repeat adjust software volume without d-pad events; play A and HOME retained");return 0;}
