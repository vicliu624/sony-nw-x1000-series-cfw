/* PC guest only. Explicit unplugged USB model; no unknown ioctl success. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#ifdef HB_RAM_USER_VOLUME
/* Observe the original manager's storage lifecycle without replacing it.
 * Only bounded paths/results are logged; mount data is never inspected. */
int mount(const char *source,const char *target,const char *type,unsigned long flags,const void *data){
 int (*next)(const char *,const char *,const char *,unsigned long,const void *)=dlsym(RTLD_NEXT,"mount");
 int result=next(source,target,type,flags,data),saved=errno;
 char line[300];int n=snprintf(line,sizeof line,"GUEST_STORAGE_MOUNT source=%.80s target=%.80s type=%.32s result=%d errno=%d caller=%p\n",source?source:"(null)",target?target:"(null)",type?type:"(null)",result,result?saved:0,__builtin_return_address(0));
 if(n>0)(void)write(2,line,(unsigned)n<sizeof line?(unsigned)n:sizeof line-1);errno=saved;return result;
}
int umount(const char *target){
 int (*next)(const char *)=dlsym(RTLD_NEXT,"umount");int result=next(target),saved=errno;
 char line[180];int n=snprintf(line,sizeof line,"GUEST_STORAGE_UMOUNT target=%.80s result=%d errno=%d caller=%p\n",target?target:"(null)",result,result?saved:0,__builtin_return_address(0));
 if(n>0)(void)write(2,line,(unsigned)n<sizeof line?(unsigned)n:sizeof line-1);errno=saved;return result;
}
int umount2(const char *target,int flags){
 int (*next)(const char *,int)=dlsym(RTLD_NEXT,"umount2");int result=next(target,flags),saved=errno;
 char line[180];int n=snprintf(line,sizeof line,"GUEST_STORAGE_UMOUNT2 target=%.80s result=%d errno=%d caller=%p\n",target?target:"(null)",result,result?saved:0,__builtin_return_address(0));
 if(n>0)(void)write(2,line,(unsigned)n<sizeof line?(unsigned)n:sizeof line-1);errno=saved;return result;
}
#endif
#ifdef HB_OMF_PARAM_RAM
#include <sys/mman.h>
static int parameter_memory=-1;
extern int guest_ftruncate(int,long) __asm__("ftruncate");
#endif
static int usb=-1,usb_writer=-1,pm=-1,pm_writer=-1,power=-1,power_writer=-1,cradle=-1,cradle_writer=-1,cradle_enabled;
#if defined(HB_NCAN_OPEN_PROBE) || defined(HB_NCAN_CONTROL_MODEL)
static int ncan_probe=-1,ncan_writer=-1;static unsigned ncan_probe_notes;
#endif
#ifdef HB_INTERDSP_OPEN_PROBE
/* Diagnostic handle only. Every DSP request fails; no DSP success is modeled. */
static int dsp_probe=-1;
static unsigned dsp_setup_seen,dsp_task_seen,dsp_read_seen;
#endif
/* F_SETFD has no time structure; bind the stock symbol explicitly. */
extern int guest_fcntl(int,int,...) __asm__("fcntl");
#ifdef HB_SILENT_MIXER_MODEL
#include "stock_silent_mixer_model.h"
#endif
#ifdef HB_MG_CONSTRUCTOR_MODEL
#include "stock_mg_constructor_model.h"
#endif
#ifdef HB_DISPLAY_TOUCH_MODEL
#include "stock_display_touch_model.h"
#endif
#ifdef HB_INTERDSP_IDLE_MODEL
#include "stock_dsp_idle_model.h"
#endif
static void note(const char *path){char line[200];int n=snprintf(line,sizeof line,"MANAGER_DEVICE OPEN %s\n",path);write(2,line,n);}
static int open_device(const char *path,int flags,unsigned mode,const char *symbol){
 int (*real_open)(const char *,int,...)=dlsym(RTLD_NEXT,symbol);
 if(!strncmp(path,"/dev/",5))note(path);
#ifdef HB_MG_CONSTRUCTOR_MODEL
 if(!strcmp(path,"/dev/mg")){
  if(mg_constructor.fd>=0){errno=EBUSY;return -1;}
  int fd=real_open("/dev/zero",flags,mode);
  if(fd>=0){mg_constructor.fd=fd;mg_constructor.mappings=mg_constructor.initialized=0;}
  return fd;
 }
#endif
#ifdef HB_SILENT_MIXER_MODEL
 if(!strcmp(path,"/dev/sound/mixer")){silent_mixer=real_open("/dev/null",flags,mode);return silent_mixer;}
 if(!strcmp(path,"/dev/sound/beep")){silent_beep=real_open("/dev/null",flags,mode);return silent_beep;}
#endif
#ifdef HB_DISPLAY_TOUCH_MODEL
 if(!strcmp(path,"/dev/fb/0")||!strcmp(path,"/dev/icx_touch_screen")||!strcmp(path,"/dev/icx_watch_elapsed_time"))return gui_open(path,flags,real_open);
#endif
#if defined(HB_NCAN_OPEN_PROBE) || defined(HB_NCAN_CONTROL_MODEL)
 if(!strcmp(path,"/dev/icx1111_ncan")){
  int ends[2];if(pipe(ends))return -1;ncan_probe=ends[0];ncan_writer=ends[1];
  guest_fcntl(ends[0],F_SETFD,FD_CLOEXEC);guest_fcntl(ends[1],F_SETFD,FD_CLOEXEC);return ncan_probe;
 }
#endif
#ifdef HB_INTERDSP_IDLE_MODEL
 if(!strcmp(path,"/dev/InterDSP/control"))return dsp_idle_open(flags);
#endif
#ifdef HB_INTERDSP_OPEN_PROBE
 if(!strcmp(path,"/dev/InterDSP/control")){
  dsp_probe=real_open("/dev/null",flags,mode);return dsp_probe;
 }
#endif
#ifdef HB_OMF_PARAM_RAM
 if(!strcmp(path,"/dev/mem")){
  parameter_memory=real_open("/tmp/omf-parameter-page",O_RDWR|O_CREAT,0600);
  if(parameter_memory>=0&&guest_ftruncate(parameter_memory,4096)){int (*real_close)(int)=dlsym(RTLD_NEXT,"close");real_close(parameter_memory);parameter_memory=-1;}
  return parameter_memory;
 }
#endif
 if(!strcmp(path,"/dev/usbconn")){
  /* Unplugged, no state change: status query returns zero, readiness must stay
   * idle. /dev/null is always readable and spins the stock realtime waiter. */
  int ends[2];if(pipe(ends))return -1;usb=ends[0];usb_writer=ends[1];
  guest_fcntl(ends[0],F_SETFD,FD_CLOEXEC);guest_fcntl(ends[1],F_SETFD,FD_CLOEXEC);return usb;
 }
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
#if defined(HB_OMF_PARAM_RAM) || defined(HB_MG_CONSTRUCTOR_MODEL)
void *guest_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
void *guest_mmap(void *address,size_t length,int prot,int flags,int fd,long offset){
 void *(*real_map)(void *,size_t,int,int,int,long)=dlsym(RTLD_NEXT,"mmap");
#ifdef HB_MG_CONSTRUCTOR_MODEL
 if(mg_constructor.fd>=0&&fd==mg_constructor.fd)return stock_mg_constructor_map(&mg_constructor,address,length,prot,flags,offset,real_map);
#endif
#ifdef HB_DISPLAY_TOUCH_MODEL
 if(gui_fb>=0&&fd==gui_fb){
  char detail[140];int count=snprintf(detail,sizeof detail,"MANAGER_DEVICE GUI_MMAP length=%lu offset=%08lx flags=%x prot=%x\n",(unsigned long)length,(unsigned long)offset,flags,prot);write(2,detail,count);
  if(address||offset||length>0x500000||prot!=(PROT_READ|PROT_WRITE)||flags!=MAP_SHARED){errno=EINVAL;return MAP_FAILED;}
  void *result=real_map(address,length,prot,flags,fd,0);if(result!=MAP_FAILED)gui_pixels=result;return result;
 }
#endif
#ifdef HB_OMF_PARAM_RAM
 if(parameter_memory>=0&&fd==parameter_memory){
  if(address||length!=4096||prot!=(PROT_READ|PROT_WRITE)||flags!=MAP_SHARED||(unsigned long)offset!=0x33a5d000){errno=ENXIO;return MAP_FAILED;}
  const char *note="MANAGER_DEVICE OMF_PARAMETER_RAM 33a5d000 4096\n";write(2,note,strlen(note));
  return real_map(address,length,prot,flags,fd,0);
 }
#endif
 return real_map(address,length,prot,flags,fd,offset);
}
#endif
int ioctl(int fd,unsigned long command,void *value){
#ifdef HB_MG_CONSTRUCTOR_MODEL
 if(mg_constructor.fd>=0&&fd==mg_constructor.fd){
  int result=stock_mg_constructor_ioctl(&mg_constructor,command,value),saved=errno;
  char line[150];int n=snprintf(line,sizeof line,"MANAGER_DEVICE MG_CONSTRUCTOR command=%08lx operation=%08x result=%d no_crypto=1\n",command,command==0x89a0&&value?*(unsigned *)value:0,result);write(2,line,n);errno=saved;return result;
 }
#endif
#ifdef HB_SILENT_MIXER_MODEL
 if(silent_beep>=0&&fd==silent_beep)return silent_beep_ioctl(command,value);
 if(silent_mixer>=0&&fd==silent_mixer){
  int result=silent_mixer_ioctl(command,value);
  if(result){int failure=errno;unsigned word=value&&((command>>16)&0x3fff)==4?*(unsigned *)value:0;char detail[180];int n=snprintf(detail,sizeof detail,"MANAGER_DEVICE SILENT_MIXER_REFUSED cmd=%08lx errno=%d value=%08x\n",command,failure,word);write(2,detail,n);errno=failure;}
  return result;
 }
#endif
#ifdef HB_DISPLAY_TOUCH_MODEL
 if((gui_fb>=0&&fd==gui_fb)||(gui_touch>=0&&fd==gui_touch)||(gui_watch>=0&&fd==gui_watch))return gui_ioctl(fd,command,value);
#endif
#if defined(HB_NCAN_OPEN_PROBE) || defined(HB_NCAN_CONTROL_MODEL)
 if(ncan_probe>=0&&fd==ncan_probe){
#ifdef HB_NCAN_CONTROL_MODEL
  if(command==0xc0046311&&value){
   unsigned requested=*(unsigned *)value;char detail[110];int length=snprintf(detail,sizeof detail,"MANAGER_DEVICE NCAN_VIRTUAL_MODE_REQUEST %u\n",requested);write(2,detail,length);
   if(requested<=1)return 0;
  }
#endif
  if(ncan_probe_notes++<16){char line[140];int n=snprintf(line,sizeof line,"MANAGER_DEVICE NCAN_PROBE_REJECT_IOCTL %08lx caller=%p\n",command,__builtin_return_address(0));write(2,line,n);}
  /* An immediately failing request can spin a stock realtime polling thread
   * and starve the UI/PID1. Diagnostic throttle only, still no ioctl success. */
  usleep(20000);errno=EOPNOTSUPP;return -1;
 }
#endif
#ifdef HB_INTERDSP_IDLE_MODEL
 if(fd==dsp_idle_fd)return dsp_idle_ioctl(command,value);
#endif
#ifdef HB_INTERDSP_OPEN_PROBE
 if(fd==dsp_probe){
  char line[100];int n=snprintf(line,sizeof line,"MANAGER_DEVICE DSP_PROBE_REJECT_IOCTL %08lx\n",command);write(2,line,n);
  unsigned *seen=command==0x40184411?&dsp_setup_seen:command==0xc0084413?&dsp_task_seen:command==0x80184401?&dsp_read_seen:0;
  if(seen&&(*seen)++<16&&value){
   /* These three pinned stock ABI requests have 24/8/24-byte arguments.
    * Capture input words only, never dereference nested DSP buffer pointers. */
   unsigned words[6]={0};memcpy(words,value,command==0xc0084413?8:24);
   char detail[180];int count=snprintf(detail,sizeof detail,"MANAGER_DEVICE DSP_PROBE_ARGS %08lx %08x %08x %08x %08x %08x %08x\n",command,words[0],words[1],words[2],words[3],words[4],words[5]);write(2,detail,count);
  }
  errno=EOPNOTSUPP;return -1;
 }
#endif
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
int close(int fd){int (*real_close)(int)=dlsym(RTLD_NEXT,"close");if(usb>=0&&fd==usb){usb=-1;real_close(usb_writer);usb_writer=-1;}if(fd==pm){pm=-1;real_close(pm_writer);pm_writer=-1;}if(fd==power){power=-1;real_close(power_writer);power_writer=-1;}if(fd==cradle){cradle=-1;real_close(cradle_writer);cradle_writer=-1;cradle_enabled=0;}
#ifdef HB_MG_CONSTRUCTOR_MODEL
 if(fd==mg_constructor.fd){mg_constructor.fd=-1;mg_constructor.mappings=mg_constructor.initialized=0;}
#endif
#ifdef HB_SILENT_MIXER_MODEL
 if(fd==silent_mixer)silent_mixer=-1;
 if(fd==silent_beep)silent_beep=-1;
#endif
#ifdef HB_DISPLAY_TOUCH_MODEL
 if(fd==gui_touch){
  gui_touch=-1;__atomic_store_n(&gui_touch_normal,0,__ATOMIC_RELEASE);
#ifdef HB_TOUCH_SERIAL
  if(gui_touch_session){__atomic_store_n(&gui_touch_session->running,0,__ATOMIC_RELEASE);gui_touch_session=0;}
  memset(gui_touch_value,0,sizeof gui_touch_value);
#else
  real_close(gui_touch_writer);
#endif
  gui_touch_writer=-1;
 }
 if(fd==gui_fb)gui_fb=-1;
 if(fd==gui_watch){gui_watch=-1;gui_watch_running=0;}
#endif
#if defined(HB_NCAN_OPEN_PROBE) || defined(HB_NCAN_CONTROL_MODEL)
 if(fd==ncan_probe){ncan_probe=-1;real_close(ncan_writer);ncan_writer=-1;}
#endif
#ifdef HB_INTERDSP_IDLE_MODEL
 if(fd==dsp_idle_fd){dsp_idle_fd=-1;real_close(dsp_idle_writer);dsp_idle_writer=-1;}
#endif
#ifdef HB_INTERDSP_OPEN_PROBE
 if(fd==dsp_probe)dsp_probe=-1;
#endif
#ifdef HB_OMF_PARAM_RAM
 if(fd==parameter_memory)parameter_memory=-1;
#endif
 return real_close(fd);}
