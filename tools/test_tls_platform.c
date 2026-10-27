#define _XOPEN_SOURCE 700
#include "../runtime/store/tls_platform.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
#include "../runtime/store/target_abi.h"
static int scenario,reads,closed;static volatile int stop;
static long clock_value;
int __wrap_open(const char *path,int flags,...){assert(!strcmp(path,"/dev/urandom")&&(flags&O_NOFOLLOW));return scenario==1?-1:42;}
int __wrap_open64(const char *path,int flags,...){return __wrap_open(path,flags);}
#ifdef HB_STORE_SONY_LIBC
int __wrap_hb_target_fstat(int fd,struct stat *out){
#else
int __wrap_fstat(int fd,struct stat *out){
#endif
 assert(fd==42);out->st_mode=scenario==2?S_IFREG:S_IFCHR;return scenario==3?-1:0;
}
#ifndef HB_STORE_SONY_LIBC
int __wrap_fstat64(int fd,void *out){return __wrap_fstat(fd,out);}
int __wrap___fstat64_time64(int fd,void *out){return __wrap_fstat(fd,out);}
#endif
ssize_t __wrap_read(int fd,void *out,size_t n){
 assert(fd==42);reads++;
 if(scenario==4)return 0;
 if(scenario==5){errno=EIO;return -1;}
 if(scenario==6&&reads==1){errno=EINTR;return -1;}
 if(n>7)n=7;
 memset(out,0x5a,n);if(scenario==7)stop=1;return (ssize_t)n;
}
int __wrap_close(int fd){assert(fd==42);closed++;return scenario==8?-1:0;}
long __wrap_time(long *out){assert(!out);return clock_value;}
int main(void){
 unsigned char seed[48];
 for(scenario=0;scenario<=9;scenario++){
  reads=closed=0;stop=scenario==9;memset(seed,0xaa,48);
  int result=hb_tls_seed(seed,&stop);
  int expected=scenario==0||scenario==6?0:scenario==7||scenario==9?-2:-1;
  assert(result==expected);assert(closed==(scenario==1||scenario==9?0:1));
  for(unsigned i=0;i<48;i++)assert(seed[i]==(expected?0:0x5a));
 }
 struct hb_tls_time value={1,2,3};clock_value=-1;
 assert(hb_tls_current_time(&value)==-3&&value.days==1&&value.seconds==2&&value.unix_seconds==3);
 clock_value=0;assert(!hb_tls_current_time(&value)&&value.days==719528&&value.seconds==0);
 clock_value=2147483647;assert(!hb_tls_current_time(&value)&&value.days==744383&&value.seconds==11647);
 return 0;
}
