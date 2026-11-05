/* Generic ARM guest fixture, not Sony storage or driver behavior. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;
static void copy(const char *from,const char *to){
 FILE *a=fopen(from,"rb"),*b=fopen(to,"wb");assert(a&&b);char data[512];size_t n;
 while((n=fread(data,1,sizeof data,a)))assert(fwrite(data,1,n,b)==n);
 assert(!ferror(a));assert(!fclose(a)&&!fclose(b));assert(!chmod(to,0700));
}
static void run(int expected){
 pid_t p=fork();assert(p>=0);if(!p){char *argv[]={"/capture",0};execve("/capture",argv,environ);_exit(127);}
 int status;assert(waitpid(p,&status,0)==p&&WIFEXITED(status)&&WEXITSTATUS(status)==expected);
}
static void run_stopped(void){
 pid_t p=fork();assert(p>=0);if(!p){char *argv[]={"/capture",0};execve("/capture",argv,environ);_exit(127);}
 usleep(200000);assert(!kill(p,SIGTERM));
 int status;assert(waitpid(p,&status,0)==p&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
 /* PID1 adopts any unreaped descendant: no leftover diagnostic child. */
 int extra;assert(waitpid(-1,&extra,WNOHANG)==-1);
}
static unsigned char output[4097];
static void read_trace(void){
 FILE *f=fopen("/contents/HOMEBREW/data/diagnostics/launcher-capture.bin","rb");assert(f);
 assert(fread(output,1,4096,f)==4096&&fgetc(f)==EOF);assert(!fclose(f));output[4096]=0;
}
int main(int argc,char **argv){
 (void)argv;
 if(argc>1){
  static const char stage[]="[X1-LAUNCH-ENTRY] main.begin\n";assert(write(2,stage,sizeof stage-1)==sizeof stage-1);
  const char *mode=getenv("CAPTURE_CHILD_MODE");
  if(mode&&!strcmp(mode,"closed")){close(2);for(;;)pause();}
  if(mode&&!strcmp(mode,"waiting")){for(;;)pause();}
  if(mode&&!strcmp(mode,"flood")){char data[128];memset(data,'x',sizeof data);for(unsigned i=0;i<100;i++)if(write(2,data,sizeof data)<0)break;}
  return 23;
 }
 run(71); /* User mount absent: no root-filesystem fallback. */
 assert(!mount("none","/contents","ramfs",0,0));
 const char *dirs[]={"/contents/HOMEBREW","/contents/HOMEBREW/data","/contents/HOMEBREW/data/diagnostics","/contents/HOMEBREW/launcher"};
 for(unsigned i=0;i<4;i++)assert(!mkdir(dirs[i],0700));
 const char *trace="/contents/HOMEBREW/data/diagnostics/launcher-capture.bin";
 const char *child="/contents/HOMEBREW/launcher/entry-trace-app";
 copy("/seed",trace);copy("/fixture-child",child);run(0);read_trace();
 assert(strstr((char *)output+32,"main.begin")&&strstr((char *)output+32,"status=5888 done=1 fault=0"));
 run(71); /* One-shot seed: do not mix a second attempt with stale output. */
 copy("/seed",trace);assert(!setenv("CAPTURE_CHILD_MODE","closed",1));run(0);read_trace();
 assert(strstr((char *)output+32,"status=15 done=1 fault=0"));
 copy("/seed",trace);assert(!setenv("CAPTURE_CHILD_MODE","waiting",1));run_stopped();read_trace();
 assert(strstr((char *)output+32,"status=15 done=1 fault=0"));
 copy("/seed",trace);assert(!setenv("CAPTURE_CHILD_MODE","flood",1));run(0);read_trace();
 assert(strstr((char *)output+32,"done=1 fault=1"));assert(!unsetenv("CAPTURE_CHILD_MODE"));
 assert(!unlink(child));copy("/seed",trace);run(0);read_trace();
 assert(strstr((char *)output+32,"EXEC_FAILED errno=2")&&strstr((char *)output+32,"status=32256 done=1 fault=0"));
 assert(!symlink("/fixture-child",child));copy("/seed",trace);run(75);read_trace();
 assert(strstr((char *)output+32,"CHILD_PATH_REFUSED"));assert(!unlink(child));
 assert(!unlink(trace)&&!symlink("/seed",trace));run(71);assert(!unlink(trace));
 copy("/seed",trace);FILE *f=fopen(trace,"r+b");assert(f&&fputc('!',f)!=EOF&&!fclose(f));run(71);
 puts("LAUNCHER_CAPTURE_SYSTEM_PASS");fflush(stdout);return 0;
}
