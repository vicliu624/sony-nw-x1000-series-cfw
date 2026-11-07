/* PC guest diagnostic only. Observe public libc termination calls, then
 * delegate unchanged. This is not an internal-address hook or a recovery path. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>
static void trace(const char *call,int value,void *caller){
 char line[160];int n=snprintf(line,sizeof line,"GUEST_EXIT_TRACE %s value=%d pid=%d caller=%p\n",call,value,getpid(),caller);write(2,line,n);
}
void abort(void){trace("abort",0,__builtin_return_address(0));void (*real)(void)=dlsym(RTLD_NEXT,"abort");real();for(;;)pause();}
void exit(int status){trace("exit",status,__builtin_return_address(0));void (*real)(int)=dlsym(RTLD_NEXT,"exit");real(status);for(;;)pause();}
int kill(int pid,int signal){
 if(signal==6||signal==11)trace("kill",signal,__builtin_return_address(0));
 int (*real)(int,int)=dlsym(RTLD_NEXT,"kill");return real(pid,signal);
}
