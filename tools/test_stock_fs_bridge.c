#define _XOPEN_SOURCE 700
#include "../runtime/store/stock_fs_bridge.h"
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
extern char *__strcpy_chk(char *,const char *,size_t);
extern char *__realpath_chk(const char *,char *,size_t);
extern int __snprintf_chk(char *,size_t,int,size_t,const char *,...);
static int error_mode,calls;
static void put32(unsigned char *p,unsigned value){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(value>>(8*i));}
static int fill(void *out) {
 calls++;if(error_mode==1){errno=5;return -1;}
 unsigned char *p=out;memset(p,0,96);put32(p,0x55667788);put32(p+4,0x11223344);
 put32(p+16,0x81a4);put32(p+20,1);put32(p+44,0x1011);put32(p+48,1);
 put32(p+88,0x9abcdef0);put32(p+92,0x12345678);if(error_mode==2)p[51]=128;return 0;
}
/* Stub the old interfaces. Never pass the legacy96-byte buffer to host stat. */
int __fxstat64(int version,int fd,void *out){if(version!=3||fd!=42)_Exit(80);return fill(out);}
int __lxstat64(int version,const char *path,void *out){if(version!=3||strcmp(path,"/fixture/app"))_Exit(81);return fill(out);}
char *realpath(const char *path,char *out) {
 static char answer[]="/fixture";
 if(!strcmp(path,"/bad")){errno=2;return 0;}
 if(!out)return answer;
 for(unsigned i=0;i<sizeof answer;i++)out[i]=answer[i];
 return out;
}
void abort(void){_Exit(99);}
int main(int argc,char **argv) {
 const char *mode=argc>1?argv[1]:"normal";size_t capacity=argc>2?(size_t)strtoul(argv[2],0,10):16;
 char buffer[16],large[4096];int written=0;
 char *(*volatile copy_fn)(char *,const char *,size_t)=__strcpy_chk;
 char *(*volatile path_fn)(const char *,char *,size_t)=__realpath_chk;
 int (*volatile print_fn)(char *,size_t,int,size_t,const char *,...)=__snprintf_chk;
 if(!strcmp(mode,"strcpy-fail")){copy_fn(buffer,"abcd",capacity);return 1;}
 if(!strcmp(mode,"snprintf-fail")){print_fn(buffer,16,2,capacity,"%s","hello");return 2;}
 if(!strcmp(mode,"realpath-fail")){path_fn("/fixture",large,capacity);return 3;}
 if(!strcmp(mode,"percent-n")){print_fn(buffer,sizeof buffer,2,sizeof buffer,"%n",&written);return 4;}
 if(!strcmp(mode,"positional-n")){print_fn(buffer,sizeof buffer,2,sizeof buffer,"%1$n",&written);return 5;}
 if(!strcmp(mode,"length-n")){long long n=0;print_fn(buffer,sizeof buffer,2,sizeof buffer,"%lln",&n);return 6;}
 if(!strcmp(mode,"bad-format")){print_fn(buffer,sizeof buffer,2,sizeof buffer,"abc%");return 7;}
 if(!strcmp(mode,"unknown-format")){print_fn(buffer,sizeof buffer,2,sizeof buffer,"%Q");return 8;}
 struct {struct hb_target_stat value;unsigned char guard[8];} out;memset(&out,0xa5,sizeof out);
 if(hb_target_fstat(42,&out.value)||calls!=1||out.value.st_dev!=0x1122334455667788ULL||
    out.value.st_size!=0x100001011LL||out.value.st_ino!=0x123456789abcdef0ULL||out.value.st_mode!=0x81a4||out.value.st_nlink!=1)return 10;
 for(unsigned i=0;i<sizeof out.guard;i++)if(out.guard[i]!=0xa5)return 11;
 if(hb_target_lstat("/fixture/app",&out.value)||calls!=2)return 12;
 struct hb_target_stat before=out.value;error_mode=1;
 if(hb_target_fstat(42,&out.value)!=-1||errno!=5||memcmp(&before,&out.value,sizeof before))return 13;
 error_mode=2;
 if(hb_target_fstat(42,&out.value)!=-1||errno!=75||memcmp(&before,&out.value,sizeof before))return 14;
 int previous=calls;
 if(hb_target_fstat(42,0)!=-1||errno!=22||calls!=previous||hb_target_lstat(0,&out.value)!=-1)return 15;
 if(copy_fn(buffer,"hello",6)!=buffer||strcmp(buffer,"hello"))return 16;
 if(print_fn(buffer,sizeof buffer,2,sizeof buffer,"%s/%s","one","two")!=7||strcmp(buffer,"one/two"))return 17;
 if(print_fn(buffer,4,2,sizeof buffer,"%s","abcdef")!=6||strcmp(buffer,"abc"))return 18;
 if(print_fn(buffer,sizeof buffer,2,sizeof buffer,"%%n")!=2||strcmp(buffer,"%n"))return 19;
 if(print_fn(0,0,2,0,"%s","hello")!=5)return 20;
 if(path_fn("/fixture",large,sizeof large)!=large||strcmp(large,"/fixture"))return 21;
 if(path_fn("/bad",large,sizeof large)||errno!=2)return 22;
 return 0;
}
