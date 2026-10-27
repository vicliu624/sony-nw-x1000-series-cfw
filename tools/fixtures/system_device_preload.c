/* Generic ARM guest test devices only. No process, exec or path translation. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <poll.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
static unsigned short pixels[0xc0000/2];
static int fb,touch,mapped,events,frames,opens;
static int launcher(void){char path[256];ssize_t n=readlink("/proc/self/exe",path,sizeof path-1);assert(n>0);path[n]=0;return strstr(path,"/launcher/app")!=0;}
#ifdef HB_DIAGNOSTIC_APP
#include "../../runtime/native/frontend.h"
#include "../../runtime/native/font.inc"
static int has_text(int x,int y,const char *s,int scale){for(;*s;s++,x+=6*scale){int g=*s>='A'&&*s<='Z'?*s-'A'+10:-1;if(g<0)continue;for(int row=0;row<7;row++)for(int column=0;column<5;column++)if((pixels[(y+row*scale)*240+x+column*scale]==0xffff)!=!!(glyph[g][row]&(1<<(4-column))))return 0;}return 1;}
#define CHILD_ROLE "DIAGNOSTICS"
#else
#define CHILD_ROLE "GRAPHICS"
#endif
static void note(const char *what){char s[128];int n=snprintf(s,sizeof s,"SYSTEM_DEVICE %s %s\n",launcher()?"LAUNCHER":CHILD_ROLE,what);assert(write(2,s,n)==n);}
int open64(const char *path,int flags,...){
 if(!strcmp(path,"/dev/fb/0")){assert(!fb&&!mapped&&!touch);fb=1;opens++;note(opens==2?"REOPEN":"OPEN");return 200;}
 if(!strcmp(path,"/dev/icx_touch_screen")){assert(fb&&!touch);touch=1;return 201;}
 unsigned mode=0;if(flags&O_CREAT){va_list ap;va_start(ap,flags);mode=va_arg(ap,unsigned);va_end(ap);}
 int (*real_open)(const char *,int,...)=dlsym(RTLD_NEXT,"open64");assert(real_open);return real_open(path,flags,mode);
}
int close(int fd){
 if(fd==200){assert(fb&&!mapped);fb=0;return 0;}
 if(fd==201){assert(touch&&!fb&&!mapped&&frames&&events%2==0);touch=0;note("RELEASED");return 0;}
 int (*real_close)(int)=dlsym(RTLD_NEXT,"close");assert(real_close);return real_close(fd);
}
void *mmap64(void *address,size_t length,int prot,int flags,int fd,long long offset){
 if(fd!=200){void *(*real_map)(void *,size_t,int,int,int,long long)=dlsym(RTLD_NEXT,"mmap64");assert(real_map);return real_map(address,length,prot,flags,fd,offset);}
 assert(!address&&length==sizeof pixels&&prot==3&&flags==1&&fd==200&&!offset&&fb&&!mapped);mapped=1;return pixels;
}
int munmap(void *address,size_t length){if(address!=pixels){int (*real_unmap)(void *,size_t)=dlsym(RTLD_NEXT,"munmap");assert(real_unmap);return real_unmap(address,length);}assert(length==sizeof pixels&&mapped);mapped=0;return 0;}
int ioctl(int fd,unsigned long request,void *argument){
 if(fd!=200&&fd!=201){int (*real_ioctl)(int,unsigned long,void *)=dlsym(RTLD_NEXT,"ioctl");assert(real_ioctl);return real_ioctl(fd,request,argument);}
 assert((fd==200&&fb)||(fd==201&&touch));unsigned *p=argument;
 switch(request){
 case 0x4602:memset(p,0,128);p[5]=0x120000;p[11]=480;break;
 case 0x4600:memset(p,0,160);p[0]=240;p[1]=432;p[6]=16;p[8]=11;p[9]=5;p[11]=5;p[12]=6;p[15]=5;break;
 case 0x80044e04:assert(p[0]==0&&p[1]==33);break;
 case 0x5404:break;
 case 0x80044e00:p[1]=0;p[2]=1;break;
 case 0x40044e01:
  assert(mapped&&p[0]==1&&p[1]==1&&p[2]==255&&!p[3]&&!p[4]&&!p[5]);frames++;
  if(!launcher()&&frames==2)assert(pixels[0]==0x0320);
  note("FRAME");
#ifdef HB_DIAGNOSTIC_APP
  if(!launcher()&&frames==1){assert(has_text(12,64,"READ ONLY STATUS",1));assert(has_text(12,150,"UNAVAILABLE",2));assert(has_text(150,200,"YES",1)&&has_text(150,228,"YES",1));note("PROC_STATUS_VALIDATED");}
#endif
  if(!launcher()&&frames==1){int fd=open("/tmp/graphics-ready",O_WRONLY|O_CREAT,0600);assert(fd>=0);assert(close(fd)==0);}
  break;
 case 0x80045401:{
  assert(events<4);unsigned x=30,y=400;
  if(events<2){x=80;y=launcher()?60:100;
#ifdef HB_DIAGNOSTIC_APP
   if(launcher()){int found=0;for(int row=0;row<HB_ROWS;row++)if(has_text(16,HB_LIST_TOP+18+row*HB_ROW_HEIGHT,"DEVICE CHECK",2)){y=HB_LIST_TOP+20+row*HB_ROW_HEIGHT;found=1;break;}assert(found);}
#endif
  }
  unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
  unsigned char *b=argument;memset(b,0,16);b[1]=events%2==0;b[2]=rx>>8;b[3]=rx;b[4]=ry>>8;b[5]=ry;events++;break;
 }
 default:assert(0);
 }
 return 0;
}
int guest_poll(struct pollfd *,nfds_t,int) __asm__("poll");
int guest_poll(struct pollfd *p,nfds_t count,int timeout){
 if(count==1&&p->fd==201){assert(touch&&events<4&&timeout==50);if(getenv("HB_SYSTEM_STOP")&&!launcher()){usleep(50000);return 0;}p->revents=POLLIN;return 1;}
 int (*real_poll)(struct pollfd *,nfds_t,int)=dlsym(RTLD_NEXT,"poll");assert(real_poll);return real_poll(p,count,timeout);
}
