// Host-only isolation experiment. Not a Sony executable or installation helper.
#define _GNU_SOURCE
#include <sched.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <linux/capability.h>
#include <grp.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#if !defined(__x86_64__)
#error Host fixture only; device execution is not implemented
#endif
static char jail[PATH_MAX], probe[PATH_MAX];
static void fatal(const char *s){perror(s);_exit(125);}
static void copy_probe(void){
 int in=open(probe,O_RDONLY|O_NOFOLLOW),out=open("app",O_WRONLY|O_CREAT|O_EXCL,0555);
 if(in<0||out<0)fatal("copy open");
 char b[8192];ssize_t n;size_t total=0;
 while((n=read(in,b,sizeof b))>0){total+=n;if(total>1024*1024)fatal("probe too large");size_t o=0;while(o<(size_t)n){ssize_t w=write(out,b+o,n-o);if(w<=0)fatal("copy write");o+=w;}}
 if(n<0)fatal("copy read");
 close(in);close(out);
}
static void directory(const char *p,mode_t mode){if(mkdir(p,mode))fatal("mkdir");}
static void limit(int what,rlim_t n){struct rlimit r={n,n};if(setrlimit(what,&r))fatal("rlimit");}
static int child(void *unused){
 (void)unused;
 // Modern host protection only. No claim that MS_PRIVATE exists in Sony 2.6.10.
 if(mount(NULL,"/",NULL,MS_REC|MS_PRIVATE,NULL))fatal("private namespace");
 if(mount("tmpfs",jail,"tmpfs",MS_NOSUID|MS_NODEV,"size=4m,nr_inodes=128,mode=0755"))fatal("root tmpfs");
 if(chdir(jail))fatal("chdir");
 copy_probe();directory("etc",0755);directory("var",0755);directory("db",0755);directory("dev",0755);directory("data",0755);
 if(symlink("/data/tmp","tmp"))fatal("symlink");
 int fd=open("etc/system-marker",O_WRONLY|O_CREAT|O_EXCL,0444);if(fd<0)fatal("marker");if(write(fd,"fixture",7)!=7)fatal("marker write");close(fd);
 if(mount("tmpfs","data","tmpfs",MS_NOSUID|MS_NODEV|MS_NOEXEC,"size=64k,nr_inodes=64,mode=0700,uid=60000,gid=60000"))fatal("data tmpfs");
 if(mkdir("data/tmp",0700)||chown("data/tmp",60000,60000))fatal("data tmp");
 if(mount(NULL,jail,NULL,MS_REMOUNT|MS_RDONLY|MS_NOSUID|MS_NODEV,NULL))fatal("root readonly");
 if(chroot(".")||chdir("/"))fatal("chroot");
 struct rlimit fds; if(getrlimit(RLIMIT_NOFILE,&fds)||fds.rlim_cur==RLIM_INFINITY)fatal("descriptor limit");
 for(rlim_t i=3;i<fds.rlim_cur;i++)close((int)i);
 limit(RLIMIT_CORE,0);limit(RLIMIT_NOFILE,32);limit(RLIMIT_FSIZE,8192);limit(RLIMIT_AS,32*1024*1024);limit(RLIMIT_NPROC,8);limit(RLIMIT_CPU,3);
 if(setgroups(0,NULL)||setresgid(60000,60000,60000)||setresuid(60000,60000,60000))fatal("drop identity");
 struct __user_cap_header_struct h={_LINUX_CAPABILITY_VERSION_1,0};struct __user_cap_data_struct d={0};
 if(syscall(SYS_capget,&h,&d)||d.effective||d.permitted||d.inheritable)fatal("capabilities remain");
 char *argv[]={"/app",NULL};char *env[]={"PATH=/","HOME=/data","TMPDIR=/tmp",NULL};
 execve("/app",argv,env);fatal("exec");return 125;
}
int main(int argc,char **argv){
 if(argc!=4||strcmp(argv[1],"--host-fixture")){fprintf(stderr,"Host fixture only: --host-fixture ROOT PROBE\n");return 64;}
 if(getuid()!=0){fprintf(stderr,"Requires root only inside the disposable host test\n");return 77;}
 if(!realpath(argv[2],jail)||!strstr(jail,"/sony-nw-x1000-series-cfw/work/isolation-fixtures/")||!realpath(argv[3],probe)){fprintf(stderr,"Refusing non-fixture paths\n");return 64;}
 struct stat st;if(lstat(jail,&st)||!S_ISDIR(st.st_mode))return 64;
 char *stack=malloc(1024*1024);if(!stack)return 125;
 pid_t pid=clone(child,stack+1024*1024,CLONE_NEWNS|SIGCHLD,NULL);if(pid<0){perror("clone");return 77;}
 int status;for(int ticks=0;ticks<100;ticks++){pid_t r=waitpid(pid,&status,WNOHANG);if(r==pid){free(stack);return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);}usleep(100000);}
 kill(pid,SIGKILL);waitpid(pid,&status,0);free(stack);return 124;
}
