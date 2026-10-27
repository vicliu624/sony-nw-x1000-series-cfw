#define _XOPEN_SOURCE 700
#include "tls_platform.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include "target_abi.h"
extern long sony_time(long *) __asm__("time");
static void wipe(unsigned char *out){volatile unsigned char *p=out;for(unsigned i=0;i<48;i++)p[i]=0;}
int hb_tls_seed(unsigned char out[48],volatile int *stop){
 if(!out)return HB_TLS_PLATFORM_IO;
 wipe(out);
 if(stop&&*stop)return HB_TLS_PLATFORM_CANCELLED;
 int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW);if(fd<0)return HB_TLS_PLATFORM_IO;
 struct stat info;int result=HB_TLS_PLATFORM_IO;
 if(fstat(fd,&info)||!S_ISCHR(info.st_mode))goto done;
 unsigned used=0;
 while(used<48){
  if(stop&&*stop){result=HB_TLS_PLATFORM_CANCELLED;goto done;}
  ssize_t n=read(fd,out+used,48-used);
  if(n<0&&errno==EINTR)continue;
  if(n<=0||n>(ssize_t)(48-used))goto done;
  used+=(unsigned)n;
 }
 result=stop&&*stop?HB_TLS_PLATFORM_CANCELLED:HB_TLS_PLATFORM_OK;
done:
 if(close(fd)&&result==HB_TLS_PLATFORM_OK)result=HB_TLS_PLATFORM_IO;
 if(result)wipe(out);
 return result;
}
int hb_tls_current_time(struct hb_tls_time *out){
 if(!out)return HB_TLS_PLATFORM_TIME;
 long now=sony_time(0);if(now<0||(unsigned long long)now>2147483647ULL)return HB_TLS_PLATFORM_TIME;
 struct hb_tls_time value;
 value.unix_seconds=(unsigned long long)now;
 value.days=719528u+(unsigned)(value.unix_seconds/86400u);
 value.seconds=(unsigned)(value.unix_seconds%86400u);*out=value;return HB_TLS_PLATFORM_OK;
}
