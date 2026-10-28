#define _DEFAULT_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_preview_owners.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_handoff.h"
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>
static int quiet(int fd,unsigned pid,uint64_t birth){unsigned i;int rc=-1;for(i=0;i<100;i++){rc=qq_preview_guard_quiet(fd,pid,birth);if(rc==1)return 1;usleep(1000);}return rc;}
int main(int argc,char **argv){
 int fd,p[2],ready[2],status;pid_t child;char b=0,path[80],data[2048];unsigned parent;uint64_t birth;ssize_t n;int statfd;
 assert(argc==2);fd=open(argv[1],O_RDWR|O_CREAT,0600);assert(fd>=0);
 assert(quiet(fd,0,0)==1);assert(qq_preview_guard_quiet(-1,0,0)<0);assert(qq_preview_guard_quiet(fd,123,0)<0);
 assert(!pipe(p)&&!pipe(ready));child=fork();assert(child>=0);
 if(!child){close(p[1]);close(ready[0]);assert(write(ready[1],"x",1)==1);assert(read(p[0],&b,1)==1);assert(!close(fd));assert(write(ready[1],"y",1)==1);assert(read(p[0],&b,1)==1);_exit(0);}
 close(p[0]);close(ready[1]);assert(read(ready[0],&b,1)==1);
 assert(qq_preview_guard_quiet(fd,0,0)==0);
 snprintf(path,sizeof(path),"/proc/%u/stat",(unsigned)child);statfd=open(path,O_RDONLY);assert(statfd>=0);n=read(statfd,data,sizeof(data)-1);assert(n>0);data[n]=0;close(statfd);
 assert(!qq_preview_process_stat(data,(unsigned)child,&parent,&birth));assert(parent==(unsigned)getpid());
 assert(quiet(fd,(unsigned)child,birth)==1);assert(qq_preview_guard_quiet(fd,(unsigned)child,birth+1)<0);
 assert(write(p[1],"x",1)==1&&read(ready[0],&b,1)==1);assert(quiet(fd,0,0)==1);
 assert(write(p[1],"x",1)==1);assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));
 close(p[1]);close(ready[0]);close(fd);return 0;
}
