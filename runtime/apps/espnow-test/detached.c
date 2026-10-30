#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "detached.h"
#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <stdio.h>
#include <errno.h>
int probe_detach(int journal_fd,const char *path,int (*run)(int)){
 if(journal_fd<0||!path||!run)return 64;
 int ready[2];if(pipe(ready)){close(journal_fd);return 71;}
 pid_t pid=fork();if(pid<0){close(ready[0]);close(ready[1]);close(journal_fd);return 71;}
 if(pid){
  close(ready[1]);close(journal_fd);unsigned char ack=0;ssize_t n;
  do{n=read(ready[0],&ack,1);}while(n<0&&errno==EINTR);close(ready[0]);
  if(n!=1||ack!=1){int status;while(waitpid(pid,&status,0)<0&&errno==EINTR){}return 71;}
  printf("job_pid=%ld journal=%s\n",(long)pid,path);return 0;
 }
 if(setsid()<0||chdir("/"))_exit(71);
 int empty=open("/dev/null",O_RDWR);if(empty<0||dup2(empty,0)<0||dup2(empty,1)<0||dup2(empty,2)<0)_exit(71);
 close(ready[0]);long limit=sysconf(_SC_OPEN_MAX);if(limit<3)_exit(71);
 for(long fd=3;fd<limit;fd++)if(fd!=journal_fd&&fd!=ready[1])close((int)fd);
 unsigned char ack=1;if(write(ready[1],&ack,1)!=1)_exit(71);close(ready[1]);
 int result=run(journal_fd);if(close(journal_fd)&&!result)result=74;_exit(result);
}
