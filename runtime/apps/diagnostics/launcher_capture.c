/* Explicit temporary diagnostic supervisor. Never installed by normal builders.
 * Only a preallocated nonce-matched user file may be written. No system log,
 * directory creation, wireless, framebuffer, database or raw-flash operations.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../../store/stock_fs_bridge.h"
#include "launcher_capture_profile.h"
extern int capture_sscanf(const char *,const char *,...) __asm__("sscanf");
extern long long capture_seek(int,long long,int) __asm__("llseek");
extern char **environ;
static const unsigned char expected[32]=LAUNCHER_CAPTURE_HEADER;
static const char trace_path[]="/contents/HOMEBREW/data/diagnostics/launcher-capture.bin";
static const char child_path[]="/contents/HOMEBREW/launcher/entry-trace-app";
static volatile sig_atomic_t stopping;
static void stop_capture(int signal_number){(void)signal_number;stopping=1;}
static int mounts_ok(void){
 FILE *f=fopen("/proc/mounts","r");if(!f)return 0;
 char line[1024],source[256],point[256],type[64],options[256];unsigned found=0,lines=0;int bad=0;
 while(fgets(line,sizeof line,f)){
  if(++lines>128||!strchr(line,'\n')||capture_sscanf(line,"%255s %255s %63s %255s",source,point,type,options)!=4){bad=1;break;}
  if(!strcmp(point,"/contents")){
   if(strcmp(source,"/dev/mtdblock/2")||strcmp(type,"vfat")||strncmp(options,"rw,",3))bad=1;
   found++;
  }else if(!strncmp(point,"/contents/",10))bad=1;
 }
 if(ferror(f))bad=1;if(fclose(f))bad=1;return !bad&&found==1;
}
static int open_trace(void){
 static const char *parts[]={"/contents","/contents/HOMEBREW","/contents/HOMEBREW/data","/contents/HOMEBREW/data/diagnostics","/contents/HOMEBREW/launcher"};
 struct hb_target_stat base,node,opened,root;
 if(!mounts_ok()||hb_target_lstat("/contents",&base)||hb_target_lstat("/",&root)||base.st_dev==root.st_dev)return -1;
 for(unsigned i=0;i<sizeof parts/sizeof *parts;i++)
  if(hb_target_lstat(parts[i],&node)||(node.st_mode&0170000)!=0040000||node.st_dev!=base.st_dev)return -1;
 if(hb_target_lstat(trace_path,&node)||(node.st_mode&0170000)!=0100000||node.st_dev!=base.st_dev||node.st_size!=4096||node.st_nlink!=1)return -1;
 int fd=open(trace_path,O_RDWR|O_NONBLOCK|O_NOFOLLOW);if(fd<0)return -1;
 unsigned char seed[4096];
 if(hb_target_fstat(fd,&opened)||opened.st_dev!=node.st_dev||opened.st_ino!=node.st_ino||opened.st_size!=4096||opened.st_nlink!=1||
    read(fd,seed,sizeof seed)!=(ssize_t)sizeof seed||memcmp(seed,expected,32)){close(fd);return -1;}
 for(unsigned i=32;i<sizeof seed;i++)if(seed[i]){close(fd);return -1;}
 if(capture_seek(fd,32,SEEK_SET)!=32){close(fd);return -1;}
 return fd;
}
static int emit(int fd,unsigned *used,const void *data,unsigned bytes){
 if(bytes>4000-*used)return -1;
 if(write(fd,data,bytes)!=(ssize_t)bytes)return -1;
 *used+=bytes;return 0;
}
int main(void){
 int fd=open_trace();if(fd<0)return 71;
 unsigned used=0;int stream[2];
 struct hb_target_stat trace,child;
 int child_result=hb_target_lstat(child_path,&child),child_error=errno;
 if(hb_target_fstat(fd,&trace)||(child_result?child_error!=ENOENT:
    ((child.st_mode&0170000)!=0100000||child.st_dev!=trace.st_dev||child.st_nlink!=1))){
  (void)emit(fd,&used,"CHILD_PATH_REFUSED\n",19);(void)fsync(fd);close(fd);return 75;
 }
 if(signal(SIGTERM,stop_capture)==SIG_ERR||signal(SIGINT,stop_capture)==SIG_ERR||signal(SIGHUP,stop_capture)==SIG_ERR){close(fd);return 76;}
 if(emit(fd,&used,"CAPTURE_BEGIN\n",14)||fsync(fd)||pipe(stream)){close(fd);return 72;}
 pid_t pid=fork();if(pid<0){close(stream[0]);close(stream[1]);close(fd);return 73;}
 if(!pid){
  close(fd);close(stream[0]);
  if(setpgid(0,0)||dup2(stream[1],2)<0)_exit(125);
  if(stream[1]!=2)close(stream[1]);
  char *argv[]={(char *)child_path,"--native",0};execve(child_path,argv,environ);
  int failure=errno;char error[64];int n=snprintf(error,sizeof error,"EXEC_FAILED errno=%d\n",failure);
  if(n>0)(void)write(2,error,(unsigned)n);_exit(126);
 }
 close(stream[1]);int status=0,done=0,fault=0;
 /* Finite 100 polls; no background session. A diagnostic test must not tap
  * app entries. Own process group only; never signal Sony's process group. */
 for(unsigned step=0;step<100&&!stopping;step++){
  struct pollfd p={stream[0],POLLIN,0};int ready=poll(&p,1,100);
  if(ready<0&&errno!=EINTR){fault=1;break;}
  if(ready>0&&(p.revents&(POLLIN|POLLHUP))){
   char data[128];ssize_t n=read(stream[0],data,sizeof data);
   if(n>0&&(used+(unsigned)n>3900||emit(fd,&used,data,(unsigned)n))){fault=1;break;}
   if(n<0&&errno!=EINTR){fault=1;break;}
   if(n==0){done=waitpid(pid,&status,WNOHANG)==pid;break;}
  }
 }
 if(!done){
  if(kill(-pid,SIGTERM)<0)(void)kill(pid,SIGTERM);
  for(unsigned i=0;i<20;i++){pid_t r=waitpid(pid,&status,WNOHANG);if(r==pid){done=1;break;}usleep(50000);}
  if(!done){if(kill(-pid,SIGKILL)<0)(void)kill(pid,SIGKILL);done=waitpid(pid,&status,0)==pid;}
 }
 close(stream[0]);char footer[80];int n=snprintf(footer,sizeof footer,"\nCAPTURE_END status=%d done=%d fault=%d\n",status,done,fault);
 int result=n<=0||emit(fd,&used,footer,(unsigned)n)||fsync(fd)?74:0;
 if(close(fd))result=74;return result;
}
