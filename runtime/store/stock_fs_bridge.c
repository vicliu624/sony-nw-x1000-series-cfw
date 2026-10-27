#include "stock_fs_bridge.h"
#include "stock_stat64.h"
#include <stddef.h>
#include <stdarg.h>
extern int sony_fxstat64(int,int,void *) __asm__("__fxstat64");
extern int sony_lxstat64(int,const char *,void *) __asm__("__lxstat64");
extern int *sony_errno(void) __asm__("__errno_location");
extern char *sony_realpath(const char *,char *) __asm__("realpath");
extern int sony_vsnprintf(char *,size_t,const char *,va_list) __asm__("vsnprintf");
extern void sony_abort(void) __asm__("abort") __attribute__((noreturn));
static int convert(const unsigned char *raw,struct hb_target_stat *out) {
 struct hb_stock_stat decoded;struct hb_target_stat value;
 if(hb_stock_stat64_decode(raw,96,3,&decoded)){*sony_errno()=75;return -1;}
 value.st_dev=decoded.device;value.st_size=(long long)decoded.size;value.st_ino=decoded.inode;
 value.st_mode=decoded.mode;value.st_nlink=decoded.links;*out=value;return 0;
}
int hb_target_fstat(int fd,struct hb_target_stat *out) {
 unsigned char raw[96] __attribute__((aligned(8)));
 if(!out){*sony_errno()=22;return -1;}
 int result=sony_fxstat64(3,fd,raw);return result?result:convert(raw,out);
}
int hb_target_lstat(const char *path,struct hb_target_stat *out) {
 unsigned char raw[96] __attribute__((aligned(8)));
 if(!out||!path){*sony_errno()=22;return -1;}
 int result=sony_lxstat64(3,path,raw);return result?result:convert(raw,out);
}
/* Runtime checks for compiler-emitted fortified calls. Do not alias these to
 * unchecked originals. The snprintf profile rejects %n (even read-only %n),
 * malformed formats and unknown extensions; current store uses literal %s. */
static int contains(const char *set,char c){for(unsigned i=0;set[i];i++)if(set[i]==c)return 1;return 0;}
static int format_ok(const char *format) {
 if(!format)return 0;
 for(unsigned i=0;format[i];i++)if(format[i]=='%') {
  i++;if(format[i]=='%')continue;
  while(format[i]&&!contains("diouxXfFeEgGaAcCsSpnm%",format[i])) {
   if(!contains("0123456789$*.+- #'hlLjztqI",format[i]))return 0;
   i++;
  }
  if(!format[i]||format[i]=='n')return 0;
 }
 return 1;
}
char *__strcpy_chk(char *out,const char *input,size_t capacity) {
 size_t n=0;if(!out||!input)sony_abort();
 while(n<capacity&&input[n])n++;
 if(n==capacity)sony_abort();
 for(size_t i=0;i<=n;i++)out[i]=input[i];
 return out;
}
char *__realpath_chk(const char *path,char *out,size_t capacity) {
 /* Stock realpath's caller-supplied buffer contract is PATH_MAX4096. */
 if(out&&capacity<4096)sony_abort();
 return sony_realpath(path,out);
}
int __snprintf_chk(char *out,size_t maximum,int flag,size_t capacity,const char *format,...) {
 (void)flag;
 if(maximum>capacity||(!out&&maximum)||!format_ok(format))sony_abort();
 va_list arguments;va_start(arguments,format);
 int result=sony_vsnprintf(out,maximum,format,arguments);va_end(arguments);return result;
}
