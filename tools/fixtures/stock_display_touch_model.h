/* PC guest-only RGB565 display adapter and idle touch controller.
 * Sony queue/geometry ABI is documented in docs/HARDWARE.md and GPL fbcommon.h.
 * Frames are copied synchronously into the generic QEMU CLCD framebuffer.
 * No video compositor, RF, audio or physical display timing is modeled.
 */
#include <linux/fb.h>
#include <stdint.h>
static int gui_fb=-1,gui_touch=-1,gui_touch_writer=-1,gui_touch_normal;
#ifdef HB_TOUCH_SERIAL
#include "stock_touch_serial.h"
#endif
static int gui_watch=-1,gui_watch_running;
static uint64_t gui_watch_base;static unsigned gui_watch_value,gui_watch_notes;
extern int gui_stock_clock32(int,void *) __asm__("clock_gettime");
static int gui_monotonic_us(uint64_t *value){
 struct {int32_t seconds,nanoseconds;} t;
 if(gui_stock_clock32(1,&t)||t.seconds<0||t.nanoseconds<0||t.nanoseconds>=1000000000){errno=EIO;return -1;}
 *value=(uint64_t)(unsigned)t.seconds*1000000+(unsigned)t.nanoseconds/1000;return 0;
}
static unsigned short *gui_pixels,*gui_clcd;
static struct fb_fix_screeninfo gui_real_fix;
static struct fb_var_screeninfo gui_real_var;
static unsigned gui_red[32],gui_green[64],gui_blue[32];
static unsigned gui_frames,gui_frame_errors;
static unsigned gui_backlight[2]={5,0},gui_modes[6]={1,1,255,0,0,0};
static int gui_open(const char *path,int flags,int (*real_open)(const char *,int,...)){
 if(!strcmp(path,"/dev/icx_watch_elapsed_time")){
  if(gui_watch>=0){errno=EBUSY;return -1;}gui_watch=real_open("/dev/null",flags,0);return gui_watch;
 }
 if(!strcmp(path,"/dev/icx_touch_screen")){
  if(gui_touch>=0){errno=EBUSY;return -1;}
  int ends[2];
#ifdef HB_TOUCH_SERIAL
  if(gui_touch_serial_start(ends))return -1;
#else
  if(pipe(ends))return -1;
#endif
  gui_touch=ends[0];gui_touch_writer=ends[1];
  guest_fcntl(ends[0],F_SETFD,FD_CLOEXEC);guest_fcntl(ends[1],F_SETFD,FD_CLOEXEC);
  if(flags&O_NONBLOCK)guest_fcntl(ends[0],F_SETFL,O_NONBLOCK);
  return gui_touch;
 }
 if(gui_fb>=0){errno=EBUSY;return -1;}
 gui_fb=real_open("/tmp/sony-qfb-model",O_RDWR|O_CREAT|O_TRUNC,0600);
 if(gui_fb<0)return -1;
 if(guest_ftruncate(gui_fb,0x500000)){int (*real_close)(int)=dlsym(RTLD_NEXT,"close");real_close(gui_fb);gui_fb=-1;}
 return gui_fb;
}
static int gui_present(unsigned *frame){
 if(!frame||frame[3]>1||frame[4]>1||frame[2]!=255||!gui_pixels){errno=EINVAL;return -1;}
 if(!gui_clcd){
  int (*real_open)(const char *,int,...)=dlsym(RTLD_NEXT,"open");
  int (*real_ioctl)(int,unsigned long,void *)=dlsym(RTLD_NEXT,"ioctl");
  int (*real_close)(int)=dlsym(RTLD_NEXT,"close");
  void *(*real_map)(void *,size_t,int,int,int,long)=dlsym(RTLD_NEXT,"mmap");
  int fd=real_open("/dev/fb0",O_RDWR,0);if(fd<0)return -1;
  if(real_ioctl(fd,0x4602,&gui_real_fix)||real_ioctl(fd,0x4600,&gui_real_var)||
     gui_real_var.xres<240||gui_real_var.yres<432||
     (gui_real_var.bits_per_pixel!=16&&gui_real_var.bits_per_pixel!=32)||
     !gui_real_var.red.length||gui_real_var.red.length>8||!gui_real_var.green.length||gui_real_var.green.length>8||!gui_real_var.blue.length||gui_real_var.blue.length>8||
     gui_real_var.red.offset+gui_real_var.red.length>gui_real_var.bits_per_pixel||gui_real_var.green.offset+gui_real_var.green.length>gui_real_var.bits_per_pixel||gui_real_var.blue.offset+gui_real_var.blue.length>gui_real_var.bits_per_pixel||
     gui_real_fix.line_length<gui_real_var.xres*(gui_real_var.bits_per_pixel/8)||
     (uint64_t)gui_real_fix.line_length*gui_real_var.yres>gui_real_fix.smem_len){real_close(fd);errno=ENOTSUP;return -1;}
  void *map=real_map(0,gui_real_fix.smem_len,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);real_close(fd);
  if(map==MAP_FAILED)return -1;gui_clcd=map;
  /* ARM926 has no divide instruction. Build the format conversion once rather
   * than doing three software divisions for every pixel of every frame. */
  for(unsigned i=0;i<32;i++){
   gui_red[i]=(i*((1u<<gui_real_var.red.length)-1)/31)<<gui_real_var.red.offset;
   gui_blue[i]=(i*((1u<<gui_real_var.blue.length)-1)/31)<<gui_real_var.blue.offset;
  }
  for(unsigned i=0;i<64;i++)gui_green[i]=(i*((1u<<gui_real_var.green.length)-1)/63)<<gui_real_var.green.offset;
 }
 unsigned left=(gui_real_var.xres-240)/2,top=(gui_real_var.yres-432)/2;
 unsigned short *page=gui_pixels+frame[3]*(0x60000/2);
 for(unsigned y=0;y<432;y++)for(unsigned x=0;x<240;x++){
  unsigned source=frame[4]?(431-y)*240+(239-x):y*240+x;
  unsigned short pixel=page[source];
  if(frame[0]&&pixel==frame[1])pixel=0;
  unsigned r=(pixel>>11)&31,g=(pixel>>5)&63,b=pixel&31;
  unsigned packed=gui_red[r]|gui_green[g]|gui_blue[b];
  unsigned char *target=(unsigned char *)gui_clcd+(top+y)*gui_real_fix.line_length+(left+x)*(gui_real_var.bits_per_pixel/8);
  for(unsigned byte=0;byte<gui_real_var.bits_per_pixel/8;byte++)target[byte]=(packed>>(byte*8))&255;
 }
 if(gui_frames++<4){const char note[]="GUEST_SONY_RGB565_FRAME_PRESENTED\n";write(2,note,sizeof note-1);}
 return 0;
}
static int gui_ioctl(int fd,unsigned long command,void *value){
 unsigned *p=value;
 if(fd==gui_watch){
  if(gui_watch_notes++<16){char note[100];int length=snprintf(note,sizeof note,"MANAGER_DEVICE GUI_WATCH_IOCTL %08lx\n",command);write(2,note,length);}
  if(command==0x4500){if(gui_monotonic_us(&gui_watch_base))return -1;gui_watch_value=0;gui_watch_running=1;return 0;}
  if(command==0x4501||command==0x80044502){
   if(gui_watch_running){uint64_t now;if(gui_monotonic_us(&now))return -1;gui_watch_value=(unsigned)((now-gui_watch_base)%380435736u);}
   if(command==0x4501)gui_watch_running=0;
   else {if(!p){errno=EFAULT;return -1;}*p=gui_watch_value;}
   return 0;
  }
  errno=EOPNOTSUPP;return -1;
 }
 char line[100];int n=snprintf(line,sizeof line,"MANAGER_DEVICE GUI_IOCTL %s %08lx\n",fd==gui_touch?"touch":"fb",command);write(2,line,n);
 if(fd==gui_touch){
  if(command==0x5404){__atomic_store_n(&gui_touch_normal,1,__ATOMIC_RELEASE);return 0;}
  if(command==0x5403||command==0x5400||command==0x5407){__atomic_store_n(&gui_touch_normal,0,__ATOMIC_RELEASE);return 0;}
  if(command==0x80045401&&p){
#ifdef HB_TOUCH_SERIAL
   unsigned char next[11];ssize_t n;
   /* The pinned original driver exposes its latest snapshot, not an edge FIFO.
    * Every reader in a frame must observe the same current contact state. */
   while((n=recv(gui_touch,next,sizeof next,MSG_DONTWAIT))==(ssize_t)sizeof next)memcpy(gui_touch_value,next,sizeof next);
   memcpy(p,gui_touch_value,11);
#else
   memset(p,0,11);
#endif
   return 0;
  }
  errno=EOPNOTSUPP;return -1;
 }
 if(!p){errno=EFAULT;return -1;}
 if(command==0x4602){
  struct fb_fix_screeninfo f;memset(&f,0,sizeof f);memcpy(f.id,"sony-qemu-ui",12);
  f.smem_len=0x500000;f.line_length=480;f.visual=FB_VISUAL_TRUECOLOR;memcpy(p,&f,sizeof f);return 0;
 }
 if(command==0x4600){
  struct fb_var_screeninfo v;memset(&v,0,sizeof v);v.xres=v.xres_virtual=240;v.yres=v.yres_virtual=432;
  v.bits_per_pixel=16;v.red.offset=11;v.red.length=5;v.green.offset=5;v.green.length=6;v.blue.length=5;
  memcpy(p,&v,sizeof v);return 0;
 }
 if(command==0x80044e00){p[1]=p[2]=0;return 0;}
 if(command==0x40044e01){
  int result=gui_present(p);
  if(result&&gui_frame_errors++<8){int failure=errno;char detail[230];int count=snprintf(detail,sizeof detail,"GUEST_GUI_FRAME_REFUSED errno=%d words=%u,%u,%u,%u,%u,%u clcd=%ux%u bpp=%u rgb=%u/%u/%u\n",failure,p[0],p[1],p[2],p[3],p[4],p[5],gui_real_var.xres,gui_real_var.yres,gui_real_var.bits_per_pixel,gui_real_var.red.offset,gui_real_var.green.offset,gui_real_var.blue.offset);write(2,detail,count);errno=failure;}
  return result;
 }
 if(command==0x40044e02){if(p[3]>1||p[4]>1||p[2]!=255){errno=EOPNOTSUPP;return -1;}memcpy(gui_modes,p,sizeof gui_modes);return 0;}
 if(command==0x80044e03){memcpy(p,gui_modes,sizeof gui_modes);return 0;}
 if(command==0x80044e04){if(p[0]>1){errno=EINVAL;return -1;}return 0;}
 if(command==0x40044e0c){if(p[0]>5){errno=EINVAL;return -1;}memcpy(gui_backlight,p,sizeof gui_backlight);return 0;}
 if(command==0x80044e0d){memcpy(p,gui_backlight,sizeof gui_backlight);return 0;}
 errno=EOPNOTSUPP;return -1;
}
