/* PC guest only. Explicit unplugged USB model; no unknown ioctl success. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifdef HB_OMF_PARAM_RAM
#include <sys/mman.h>
static int parameter_memory=-1;
extern int guest_ftruncate(int,long) __asm__("ftruncate");
#endif
static int usb=-1,pm=-1,pm_writer=-1,power=-1,power_writer=-1,cradle=-1,cradle_writer=-1,cradle_enabled;
/* F_SETFD has no time structure; bind the stock symbol explicitly. */
extern int guest_fcntl(int,int,...) __asm__("fcntl");
static void note(const char *path){char line[200];int n=snprintf(line,sizeof line,"MANAGER_DEVICE OPEN %s\n",path);write(2,line,n);}
static int open_device(const char *path,int flags,unsigned mode,const char *symbol){
 int (*real_open)(const char *,int,...)=dlsym(RTLD_NEXT,symbol);
 if(!strncmp(path,"/dev/",5))note(path);
#ifdef HB_OMF_PARAM_RAM
 if(!strcmp(path,"/dev/mem")){
  parameter_memory=real_open("/tmp/omf-parameter-page",O_RDWR|O_CREAT,0600);
  if(parameter_memory>=0&&guest_ftruncate(parameter_memory,4096)){int (*real_close)(int)=dlsym(RTLD_NEXT,"close");real_close(parameter_memory);parameter_memory=-1;}
  return parameter_memory;
 }
#endif
 if(!strcmp(path,"/dev/usbconn")){usb=real_open("/dev/null",flags,mode);return usb;}
 if(!strcmp(path,"/dev/icx1087_power")){
  /* Test-only steady battery: no charger, USB or adapter, gauge 4/4.
     Read-only queries below match stock power.h and module ioctl stores. */
  int endpoints[2];if(pipe(endpoints))return -1;power=endpoints[0];power_writer=endpoints[1];
  guest_fcntl(power,F_SETFD,FD_CLOEXEC);guest_fcntl(power_writer,F_SETFD,FD_CLOEXEC);return power;
 }
 if(!strcmp(path,"/dev/icx1087_cradle")){
  int endpoints[2];if(pipe(endpoints))return -1;cradle=endpoints[0];cradle_writer=endpoints[1];
  guest_fcntl(cradle,F_SETFD,FD_CLOEXEC);guest_fcntl(cradle_writer,F_SETFD,FD_CLOEXEC);return cradle;
 }
 if(!strcmp(path,"/dev/pm")){
  /* GPL mp200_pm_ext starts with wake_up=0, nStatus=0. An empty pipe
     models only that idle readiness state; no suspend/resume is modeled. */
  int endpoints[2];if(pipe(endpoints))return -1;pm=endpoints[0];pm_writer=endpoints[1];
  guest_fcntl(pm,F_SETFD,FD_CLOEXEC);guest_fcntl(pm_writer,F_SETFD,FD_CLOEXEC);return pm;
 }
 return real_open(path,flags,mode);
}
int guest_open(const char *,int,...) __asm__("open");
int guest_open64(const char *,int,...) __asm__("open64");
int guest_open(const char *path,int flags,...){unsigned mode=0;if(flags&O_CREAT){va_list args;va_start(args,flags);mode=va_arg(args,unsigned);va_end(args);}return open_device(path,flags,mode,"open");}
int guest_open64(const char *path,int flags,...){unsigned mode=0;if(flags&O_CREAT){va_list args;va_start(args,flags);mode=va_arg(args,unsigned);va_end(args);}return open_device(path,flags,mode,"open64");}
#ifdef HB_OMF_PARAM_RAM
void *guest_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
void *guest_mmap(void *address,size_t length,int prot,int flags,int fd,long offset){
 void *(*real_map)(void *,size_t,int,int,int,long)=dlsym(RTLD_NEXT,"mmap");
 if(parameter_memory>=0&&fd==parameter_memory){
  if(address||length!=4096||prot!=(PROT_READ|PROT_WRITE)||flags!=MAP_SHARED||(unsigned long)offset!=0x33a5d000){errno=ENXIO;return MAP_FAILED;}
  const char *note="MANAGER_DEVICE OMF_PARAMETER_RAM 33a5d000 4096\n";write(2,note,strlen(note));
  return real_map(address,length,prot,flags,fd,0);
 }
 return real_map(address,length,prot,flags,fd,offset);
}
#endif
int ioctl(int fd,unsigned long command,void *value){
 if(fd==cradle){
  char line[100];int n=snprintf(line,sizeof line,"MANAGER_DEVICE CRADLE_IOCTL %08lx\n",command);write(2,line,n);
  if(command==0x6303){cradle_enabled=1;return 0;}
  if(command==0x6302){cradle_enabled=0;return 0;}
  if(command==0x800c6301&&value){unsigned *p=value;p[0]=p[1]=p[2]=0;return 0;}
  errno=EOPNOTSUPP;return -1;
 }
 if(fd==power){
  char line[100];int n=snprintf(line,sizeof line,"MANAGER_DEVICE POWER_IOCTL %08lx\n",command);write(2,line,n);
  if(value&&(command==0x80045000||command==0x80045003||command==0x80045006)){
   *(unsigned *)value=command==0x80045003?5:0;return 0;
  }
  errno=EOPNOTSUPP;return -1;
 }
 if(fd==pm){
  char line[100];int n=snprintf(line,sizeof line,"MANAGER_DEVICE PM_IOCTL %08lx\n",command);write(2,line,n);
  if(command==0x80047000&&value){*(unsigned *)value=0;return 0;}
  errno=EOPNOTSUPP;return -1;
 }
 if(fd==usb){
  char line[100];int n=snprintf(line,sizeof line,"MANAGER_DEVICE USB_IOCTL %08lx\n",command);write(2,line,n);
  if(command==0x80046701&&value){*(unsigned *)value=0;return 0;}
  /* Access-control commands are not modeled by this startup-only backend. */
  errno=EOPNOTSUPP;return -1;
 }
 int (*real_ioctl)(int,unsigned long,void *)=dlsym(RTLD_NEXT,"ioctl");return real_ioctl(fd,command,value);
}
int close(int fd){int (*real_close)(int)=dlsym(RTLD_NEXT,"close");if(fd==usb)usb=-1;if(fd==pm){pm=-1;real_close(pm_writer);pm_writer=-1;}if(fd==power){power=-1;real_close(power_writer);power_writer=-1;}if(fd==cradle){cradle=-1;real_close(cradle_writer);cradle_writer=-1;cradle_enabled=0;}
#ifdef HB_OMF_PARAM_RAM
 if(fd==parameter_memory)parameter_memory=-1;
#endif
 return real_close(fd);}
