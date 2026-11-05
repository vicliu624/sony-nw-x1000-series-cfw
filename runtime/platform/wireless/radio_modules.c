#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
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
#ifndef XW_NATIVE_BOOT_MODULES
#define XW_NATIVE_BOOT_MODULES "/proc/modules"
#endif
static int radio_module(const char *name){
 static const char *names[]={"wlan_pwr_ctrl","wlan_pm_register","mp200_sdio","sd8xxx"};
 for(unsigned i=0;i<4;i++){
  if(!strcmp(name,names[i]))return 1;
 }
 return 0;
}
__attribute__((weak)) int xw_wireless_modules_unloaded(void){
 int fd=boot_open(XW_NATIVE_BOOT_MODULES,O_RDONLY|O_NONBLOCK|O_NOFOLLOW);if(fd<0)return 0;
 if(boot_fcntl(fd,F_SETFD,FD_CLOEXEC)<0){boot_close(fd);return 0;}
 char buffer[256],name[64];unsigned length=0,total=0;int first=1,rest=0,result=0;
 for(unsigned attempt=0;attempt<96;attempt++){
  ssize_t count=boot_read(fd,buffer,sizeof buffer);
  if(count<0){if(errno==EINTR)continue;break;}
  if(!count){result=first&&!length;break;}
  total+=(unsigned)count;if(total>16384)break;
  for(ssize_t i=0;i<count;i++){
   unsigned char c=buffer[i];
   if(c=='\n'){
    if(first||!length||!rest)goto done;
    first=1;length=0;rest=0;
   }else if(first){
    if(c==' '||c=='\t'){
     if(!length)goto done;
     name[length]=0;
     if(radio_module(name))goto done;
     first=0;
    }else{
     if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-')||length>=sizeof name-1)goto done;
     name[length++]=(char)c;
    }
   }else rest=1;
  }
 }
done:boot_close(fd);return result;
}
