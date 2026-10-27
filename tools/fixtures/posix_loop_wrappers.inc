#include <errno.h>
#include <sys/mman.h>
#include <poll.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
extern pid_t __real_fork(void);
extern pid_t __real_waitpid(pid_t,int *,int);
extern int __real_kill(pid_t,int);
extern int __real_execve(const char *,char *const[],char *const[]);
pid_t __wrap_fork(void) {
 pid_t pid=__real_fork();if(pid>0)direct_child=pid;return pid;
}
pid_t __wrap_waitpid(pid_t pid,int *status,int options) {
 pid_t result=__real_waitpid(pid,status,options);
 if(result>0){assert(result==direct_child);reaped_count++;last_wait_status=*status;}
 return result;
}
int __wrap_kill(pid_t pid,int sig) {
 assert(pid==-direct_child&&sig==SIGTERM&&direct_child>0);
 group_signals++;return __real_kill(pid,sig);
}
int __wrap_execve(const char *path,char *const args[],char *const env[]) {
 (void)args;
 assert(!owned&&!fb_open&&!touch_open&&maps==unmaps&&!owned_file_count);
 char *bridge[]={"/usr/bin/qemu-arm","-cpu","arm926","-strace",LOADER,"--library-path",LIBRARY,(char*)path,0};
 return __real_execve(bridge[0],bridge,env);
}
extern int __real_open64(const char *,int,...);
extern int __real_close(int);
int __wrap_open64(const char *path,int flags,...) {
 if(!strncmp(path,"/dev/",5)){
  long n=__wrap_x1000_oabi_call(5,(long)path,flags,0,0,0,0);
  if(n<0){errno=-n;return -1;}return (int)n;
 }
 int fd=__real_open64(path,flags);
 if(fd>=0){assert(fd<256&&fd!=10&&fd!=70&&!owned_files[fd]);owned_files[fd]=1;owned_file_count++;}
 return fd;
}
int __wrap_close(int fd) {
 if(fd==10||fd==70){long n=__wrap_x1000_oabi_call(6,fd,0,0,0,0,0);if(n<0){errno=-n;return -1;}return 0;}
 assert(fd>=0&&fd<256&&owned_files[fd]);
 int result=__real_close(fd);assert(result==0);owned_files[fd]=0;owned_file_count--;return result;
}


int __wrap_ioctl(int fd,unsigned long command,void *value){long n=__wrap_x1000_oabi_call(54,fd,command,(long)value,0,0,0);if(n<0){errno=-n;return -1;}return n;}
void *__wrap_mmap64(void *address,size_t length,int prot,int flags,int fd,off_t offset){assert(!address&&!offset);long n=__wrap_x1000_oabi_call(192,0,length,prot,flags,fd,0);if(n<0&&n>=-4095){errno=-n;return MAP_FAILED;}return (void*)n;}
int __wrap_munmap(void *p,size_t length){long n=__wrap_x1000_oabi_call(91,(long)p,length,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}
int __wrap_poll(struct pollfd *p,nfds_t count,int timeout){long n=__wrap_x1000_oabi_call(168,(long)p,count,timeout,0,0,0);if(n<0){errno=-n;return -1;}return n;}
