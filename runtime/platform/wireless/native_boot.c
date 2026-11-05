#define _DEFAULT_SOURCE
#include "native_boot.h"
#include "mode_policy.h"
#include "radio_modules.h"
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#ifdef XW_NATIVE_BOOT_FIXTURE
extern int boot_open(const char *,int,...);
extern ssize_t boot_read(int,void *,size_t);
extern int boot_close(int);
extern int boot_fcntl(int,int,...);
#else
extern int boot_open(const char *,int,...) __asm__("open");
extern ssize_t boot_read(int,void *,size_t) __asm__("read");
extern int boot_close(int) __asm__("close");
extern int boot_fcntl(int,int,...) __asm__("fcntl");
#endif
__attribute__((weak)) int xw_native_boot_manager_state(void){return ((int (*)(void))0xda18u)();}
__attribute__((weak)) int xw_native_boot_flag(void){
 unsigned char flag=255;
 ((void (*)(unsigned,unsigned,unsigned char *))0x37f5cu)(6,0x600,&flag);
 return flag<=1?flag:-1;
}
static int readonly(const char *path){
 int fd=boot_open(path,O_RDONLY|O_NONBLOCK|O_NOFOLLOW);if(fd<0)return -1;
 if(boot_fcntl(fd,F_SETFD,FD_CLOEXEC)<0){boot_close(fd);return -1;}return fd;
}
__attribute__((weak)) int xw_native_boot_radio_unloaded(void){
 return xw_wireless_modules_unloaded();
}
__attribute__((weak)) int xw_native_boot_observe(struct xw_native_boot_observation *out){
 if(!out)return XW_MODE_INVALID;
 struct xw_native_boot_observation o={0};o.before=o.after=-1;
 o.before=xw_native_boot_manager_state();
 if(o.before==2){o.modules_clear=xw_native_boot_radio_unloaded();o.after=xw_native_boot_manager_state();}
 if(o.before==2&&o.after==2&&o.modules_clear){
  int fd=readonly("/dev/urandom");
  if(fd>=0){
   unsigned char entropy[8];unsigned used=0;
   for(unsigned attempt=0;attempt<4&&used<8;attempt++){
    ssize_t count=boot_read(fd,entropy+used,8-used);
    if(count>0)used+=(unsigned)count;else if(count==0||errno!=EINTR)break;
   }
   boot_close(fd);
   if(used==8){for(unsigned i=0;i<8;i++)o.generation|=(uint64_t)entropy[i]<<(8*i);o.entropy_valid=o.generation!=0;}
  }
 }
 *out=o;return o.before==2&&o.after==2&&o.modules_clear==1&&o.entropy_valid==1?0:XW_MODE_DENIED;
}
int xw_native_boot_mode(const struct xw_native_boot_observation *o,int flag,int *mode){
 if(!o||!mode)return XW_MODE_INVALID;
 if(!o->generation||o->before!=2||o->after!=2||o->modules_clear!=1||o->entropy_valid!=1||(flag!=0&&flag!=1))return XW_MODE_DENIED;
 *mode=flag==0?XW_WIRELESS_MODE_WIFI:XW_WIRELESS_MODE_OFF;return 0;
}
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i));}
static uint32_t get32(const unsigned char *p){uint32_t n=0;for(unsigned i=0;i<4;i++)n|=(uint32_t)p[i]<<(8*i);return n;}
int xw_native_boot_encode(unsigned char raw[64],const struct xw_native_boot_observation *o){
 if(!raw||!o)return XW_MODE_INVALID;memset(raw,0,64);memcpy(raw,"WBS1",4);put32(raw+4,1);
 put32(raw+8,(uint32_t)o->generation);put32(raw+12,(uint32_t)(o->generation>>32));
 put32(raw+16,(uint32_t)o->before);put32(raw+20,(uint32_t)o->after);put32(raw+24,o->modules_clear);put32(raw+28,o->entropy_valid);return 0;
}
int xw_native_boot_decode(struct xw_native_boot_observation *out,const unsigned char *raw,unsigned bytes){
 if(!out||!raw||bytes!=64||memcmp(raw,"WBS1",4)||get32(raw+4)!=1)return XW_MODE_INVALID;
 for(unsigned i=32;i<64;i++)if(raw[i])return XW_MODE_INVALID;
 struct xw_native_boot_observation o={(uint64_t)get32(raw+8)|(uint64_t)get32(raw+12)<<32,(int32_t)get32(raw+16),(int32_t)get32(raw+20),get32(raw+24),get32(raw+28)};
 if(o.modules_clear>1||o.entropy_valid>1)return XW_MODE_INVALID;*out=o;return 0;
}
