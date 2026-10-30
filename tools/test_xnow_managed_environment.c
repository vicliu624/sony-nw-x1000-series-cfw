#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#define main full_control_checks
#include "test_xnow_full_control.c"
#undef main
#include "../runtime/platform/espnow/xnow_managed_process.h"
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
extern int env_fcntl(int,int,...) __asm__("fcntl");
int __wrap_hb_process_run_observed(const char *a,const char *b,char *const env[],volatile int *stop,const struct hb_process_observer *o){(void)a;(void)b;(void)env;(void)stop;(void)o;return -1;} /* known pre-fork failure */
int main(void){
 unsetenv("XNOW_HANDOFF_FD");unsetenv("XNOW_HANDOFF_COOKIE");int writer=999;uint8_t parsed[16];memset(parsed,0xa5,sizeof(parsed));assert(xnow_managed_process_inherited(&writer,parsed)==XNOW_IDENTITY&&writer==999&&parsed[0]==0xa5);
 uint8_t cookie[16]={1,2,3};struct xnow_handoff h;assert(!xnow_handoff_create(&h,cookie));char fd[32];snprintf(fd,sizeof(fd),"%d",h.writer);assert(!setenv("XNOW_HANDOFF_FD",fd,1));assert(!setenv("XNOW_HANDOFF_COOKIE","01020300000000000000000000000000",1));assert(!xnow_managed_process_inherited(&writer,parsed)&&writer==h.writer&&!memcmp(parsed,cookie,16));assert(env_fcntl(writer,F_GETFD)&FD_CLOEXEC);
 const char *invalid[]={"-1","2","999999999999999999999999","bad"};for(unsigned i=0;i<4;i++){assert(!setenv("XNOW_HANDOFF_FD",invalid[i],1));writer=999;assert(xnow_managed_process_inherited(&writer,parsed)==XNOW_IDENTITY&&writer==999);}
 assert(!setenv("XNOW_HANDOFF_FD",fd,1));const char *tokens[]={"","010203","00000000000000000000000000000000","g1020300000000000000000000000000"};for(unsigned i=0;i<4;i++){assert(!setenv("XNOW_HANDOFF_COOKIE",tokens[i],1));assert(xnow_managed_process_inherited(&writer,parsed)==XNOW_IDENTITY);}
 struct xnow_managed_process process;volatile int stop=0;char *bad1[]={"XNOW_HANDOFF_FD=3",0},*bad2[]={"XNOW_HANDOFF_COOKIE=x",0};assert(xnow_managed_process_begin(&process,"/unused","/unused/app",bad1,&stop,0,cookie)==XNOW_ARGUMENT);assert(xnow_managed_process_begin(&process,"/unused","/unused/app",bad2,&stop,0,cookie)==XNOW_ARGUMENT);
 char *many[130];for(unsigned i=0;i<129;i++)many[i]="X=1";many[129]=0;assert(xnow_managed_process_begin(&process,"/unused","/unused/app",many,&stop,0,cookie)==XNOW_ARGUMENT);
 assert(xnow_managed_process_begin(&process,"/unused","/unused/app",0,&stop,0,cookie)==XNOW_IO&&!process.started&&process.handoff.reader==-1&&process.handoff.writer==-1);
 assert(!xnow_handoff_close(&h));unsetenv("XNOW_HANDOFF_FD");unsetenv("XNOW_HANDOFF_COOKIE");
 puts("Managed launch capability: inherited FIFO/cookie, CLOEXEC, bad FD/token and reserved/bounded environment rejection passed; no app exec or device access.");return 0;
}

