/* Analysis-only PID-preserving startup wrapper; never installed by SDK setup. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#ifndef XW_PLAYER_STOCK_EXECUTABLE
#define XW_PLAYER_STOCK_EXECUTABLE "/usr/local/bin/SpiderApp.stock"
#endif
#ifndef XW_PLAYER_PRELOAD_LIBRARY
#define XW_PLAYER_PRELOAD_LIBRARY "/usr/local/lib/libx1000-player.so"
#endif
static int already_listed(const char *list,const char *path){
 size_t n=strlen(path);while(list&&*list){while(*list==':'||*list==' '||*list=='\t')list++;const char *end=list;while(*end&&*end!=':'&&*end!=' '&&*end!='\t')end++;if((size_t)(end-list)==n&&!memcmp(list,path,n))return 1;list=end;}return 0;
}
static void prepare_preload(void){
 const char *path=XW_PLAYER_PRELOAD_LIBRARY;
 if(access(path,R_OK))return;
 const char *prior=getenv("LD_PRELOAD");if(already_listed(prior,path))return;
 size_t a=strlen(path),b=prior?strlen(prior):0;if(b>SIZE_MAX-a-2)return;
 char *joined=malloc(a+b+2);if(!joined)return;
 memcpy(joined,path,a);size_t used=a;if(b){joined[used++]=':';memcpy(joined+used,prior,b);used+=b;}joined[used]=0;
 /* setenv copies the value; on failure retain the caller's environment. */
 (void)setenv("LD_PRELOAD",joined,1);free(joined);
}
int main(int argc,char **argv){
 prepare_preload();
 char *fallback[]={"SpiderApp",0};
 execv(XW_PLAYER_STOCK_EXECUTABLE,argc>0?argv:fallback);
 perror("original player exec");return 127;
}
