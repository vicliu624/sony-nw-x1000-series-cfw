/* PC/QEMU only. Virtual PCM/mixer and exposed FAT metadata. Never deployed. */
#define _GNU_SOURCE
#include "../../runtime/platform/pcm_output.h"
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/vfs.h>
#include <unistd.h>
extern long x1000_oabi_call(long,long,long,long,long,long,long);
static int settings[5]={0,6,1,0x3232,0x2020};
static int mix_open,dsp_open,sink=-1;static unsigned bytes;
static const char *translated(const char *p,char out[1024]){
 const char *prefix=getenv("HB_TEST_PREFIX");assert(prefix);
 if(!strncmp(p,"/contents",9)||!strcmp(p,"/proc/mounts")){
  assert(strlen(prefix)+strlen(p)<1024);strcpy(out,prefix);strcat(out,p);return out;
 }return p;
}
static void note(const char *p){assert(x1000_oabi_call(4,2,(long)p,strlen(p),0,0,0)==(long)strlen(p));}
int open64(const char*p,int flags,...){
 if(!strcmp(p,"/dev/sound/mixer")){assert(flags==2&&!mix_open);mix_open=1;note("PCM MIXER OPEN\n");return 300;}
 if(!strcmp(p,"/dev/sound/dsp")){assert(flags==(1|0x800)&&!dsp_open);if(getenv("PCM_BUSY")){errno=EBUSY;return -1;}dsp_open=1;note("PCM DSP OPEN NONBLOCK\n");return 301;}
 char path[1024];p=translated(p,path);unsigned mode=0;if(flags&O_CREAT){va_list a;va_start(a,flags);mode=va_arg(a,unsigned);va_end(a);}int(*next)(const char*,int,...)=dlsym(RTLD_NEXT,"open64");return next(p,flags,mode);
}
FILE*fopen64(const char*p,const char*m){char path[1024];p=translated(p,path);FILE*(*next)(const char*,const char*)=dlsym(RTLD_NEXT,"fopen64");return next(p,m);}
char*realpath(const char*p,char*out){if(!strncmp(p,"/contents",9)){assert(out);strcpy(out,p);return out;}char*(*next)(const char*,char*)=dlsym(RTLD_NEXT,"realpath");return next(p,out);}
/* QEMU's -L lookup follows dangling fixture symlinks when deciding whether
 * to redirect. Explicitly translate readlink metadata paths, not its results. */
ssize_t readlink(const char*p,char*out,size_t n){char path[1024];if(!strncmp(p,"/proc/",6)){const char*prefix=getenv("HB_TEST_PREFIX");assert(prefix&&strlen(prefix)+strlen(p)<sizeof path);strcpy(path,prefix);strcat(path,p);p=path;}long r=x1000_oabi_call(85,(long)p,(long)out,n,0,0,0);if(r<0){errno=-r;return -1;}return r;}
int __lxstat64(int version,const char*p,void*out){assert(version==3);char path[1024];p=translated(p,path);long r=x1000_oabi_call(196,(long)p,(long)out,0,0,0,0);if(r<0){errno=-r;return -1;}return 0;}
int statfs64(const char*p,struct statfs64*out){assert(!strncmp(p,"/contents",9));memset(out,0,sizeof(*out));out->f_type=0x4d44;out->f_bsize=4096;out->f_bavail=100000;return 0;}
int ioctl(int fd,unsigned long command,void*arg){
 if(fd!=300&&fd!=301){int(*next)(int,unsigned long,void*)=dlsym(RTLD_NEXT,"ioctl");return next(fd,command,arg);}
 if(fd==301){assert(dsp_open);if(command==HB_PCM_RESET){note("PCM RESET\n");return 0;}int*v=arg;
  if(command==HB_PCM_FORMAT)assert(*v==16);else if(command==HB_PCM_CHANNELS)assert(*v==2);else if(command==HB_PCM_SPEED)assert(*v==22050);else assert(command==HB_PCM_FRAGMENT&&*v==((8<<16)|10));return 0;
 }
 assert(mix_open);int*v=arg;
 if(command==FM_AUDIO_GET_CODEC_POWERDOWN){*v=0;return 0;}
 unsigned gets[]={FM_AUDIO_GET_MUTE,FM_AUDIO_GET_SOURCE,FM_AUDIO_GET_OUTPUT,FM_AUDIO_GET_PCM,FM_AUDIO_GET_ADC};
 unsigned sets[]={FM_AUDIO_SET_MUTE,FM_AUDIO_SET_SOURCE,FM_AUDIO_SET_OUTPUT,FM_AUDIO_SET_PCM,FM_AUDIO_SET_ADC};
 for(unsigned i=0;i<5;i++){if(command==gets[i]){*v=settings[i];return 0;}if(command==sets[i]){settings[i]=*v;return 0;}}
 assert(0);return -1;
}
ssize_t write(int fd,const void*p,size_t n){
 if(fd!=301){ssize_t(*next)(int,const void*,size_t)=dlsym(RTLD_NEXT,"write");return next(fd,p,n);}
 assert(dsp_open&&n&&n<=8192);if(sink<0){const char*path=getenv("PCM_CAPTURE");assert(path);sink=(int)x1000_oabi_call(5,(long)path,577,0600,0,0,0);assert(sink>=0);}
 /* Force a short write, preserving every sample byte through the real queue. */
 if(n>126)n=126;
 assert(x1000_oabi_call(4,sink,(long)p,n,0,0,0)==(long)n);bytes+=(unsigned)n;return (ssize_t)n;
}
int close(int fd){
 if(fd==301){assert(dsp_open);dsp_open=0;if(sink>=0){assert(!x1000_oabi_call(6,sink,0,0,0,0,0));sink=-1;}assert(bytes>100);note("PCM AUDIO CAPTURED\n");return 0;}
 if(fd==300){assert(mix_open&&!dsp_open);int saved[]={0,6,1,0x3232,0x2020};assert(!memcmp(saved,settings,sizeof saved));mix_open=0;note("PCM MIXER RESTORED\n");return 0;}
 int(*next)(int)=dlsym(RTLD_NEXT,"close");return next(fd);
}
