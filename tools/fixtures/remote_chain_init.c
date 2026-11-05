/* PID1 only inside the isolated ARM guest; all writes target guest RAM. */
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <assert.h>
#include <string.h>
#ifdef XW_FORMAL_REMOTE_LAYOUT
#define REMOTE_PARENT "/contents/HOMEBREW/data/wireless-remote"
#define REMOTE_DIRECTORY REMOTE_PARENT "/runtime"
#else
#define REMOTE_PARENT "/contents/HOMEBREW/data/player-sdk-live-1"
#define REMOTE_DIRECTORY REMOTE_PARENT "/remote"
#endif
static void unchanged(void){
 int a=open("/stage/config.bin",O_RDONLY),b=open(REMOTE_DIRECTORY "/config.bin",O_RDONLY);
 assert(a>=0&&b>=0);char first[80],second[80],extra;
 assert(read(a,first,80)==80&&read(b,second,80)==80&&!memcmp(first,second,80));
 assert(read(a,&extra,1)==0&&read(b,&extra,1)==0&&!close(a)&&!close(b));
 puts("REMOTE_CONFIG_UNCHANGED");
}
static void copy(const char *source,const char *target){
 int a=open(source,O_RDONLY),b=open(target,O_WRONLY|O_CREAT|O_EXCL,0700);assert(a>=0&&b>=0);char buffer[4096];ssize_t n;
 while((n=read(a,buffer,sizeof buffer))>0){ssize_t used=0;while(used<n){ssize_t k=write(b,buffer+used,(size_t)(n-used));assert(k>0);used+=k;}}assert(!n&&!close(a)&&!close(b));
}
int main(void){
 assert(!mount("proc","/proc","proc",0,0));assert(!mkdir("/contents",0700));
 assert(!mount("none","/contents","tmpfs",0,"size=8m"));assert(!mkdir("/tmp",0700));
 const char *dirs[]={"/contents/HOMEBREW","/contents/HOMEBREW/data",REMOTE_PARENT,REMOTE_DIRECTORY};
 for(unsigned i=0;i<4;i++)assert(!mkdir(dirs[i],0700));
 copy("/stage/service.arm",REMOTE_DIRECTORY "/service.arm");
 copy("/stage/owner.arm",REMOTE_DIRECTORY "/owner.arm");
 copy("/stage/config.bin",REMOTE_DIRECTORY "/config.bin");
 char *args[]={"/test","--startup-remote-probe","/supervisor","/tmp/x1000-player-chain","0123456789abcdef0123456789abcdef","23","--charger-confirmed","--exclusive-radio-confirmed",0};
#ifdef XW_DIRECT_REMOTE
#if defined(XW_DIRECT_BAD_GENERATION)
 char *direct_args[]={"/test","--direct-remote-bad-generation","/supervisor",0};
#elif defined(XW_DIRECT_BAD_GRANTS)
 char *direct_args[]={"/test","--direct-remote-bad-grants","/supervisor",0};
#else
 char *direct_args[]={"/test","--direct-remote-probe","/supervisor",0};
#endif
#endif
 char *env[]={"LD_LIBRARY_PATH=/lib",0};int child=fork();assert(child>=0);if(!child){
#ifdef XW_DIRECT_REMOTE
  (void)args;execve(direct_args[0],direct_args,env);
#else
  execve(args[0],args,env);
#endif
  _exit(127);}
 int status;assert(waitpid(child,&status,0)==child);unchanged();printf("REMOTE_CHAIN_CHILD_STATUS=%d\n",status);fflush(stdout);for(;;)pause();
}
