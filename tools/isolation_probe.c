// Host-only test workload; it receives no actual device nodes.
#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mount.h>
#include <sys/sysmacros.h>
#include <sys/resource.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
static int failed;
static void check(const char *name,int ok){printf("%s %s\n",ok?"PASS":"FAIL",name);if(!ok)failed++;}
static int write_denied(const char *p){int fd=open(p,O_WRONLY|O_CREAT,0600);if(fd>=0){close(fd);return 0;}return errno==EROFS||errno==EACCES||errno==ENOENT;}
int main(void){
 setbuf(stdout,NULL);signal(SIGXFSZ,SIG_IGN);
 check("identity",getuid()==60000&&geteuid()==60000&&getgid()==60000);
 check("cannot_regain_root",setuid(0)==-1);
 check("system_readonly",write_denied("/etc/system-marker"));
 check("var_hidden_readonly",write_denied("/var/x"));check("db_hidden_readonly",write_denied("/db/x"));
 check("raw_flash_not_exposed",write_denied("/dev/mtdblock/1"));
 check("nvp_not_exposed",write_denied("/dev/icx1087_nvp/9"));
 check("proc_not_exposed",access("/proc/self/fd",F_OK)==-1);
 check("cwd_escape_denied",write_denied("/../../etc/escape-marker"));
 check("mount_denied",mount("none","/data","tmpfs",0,NULL)==-1);
 check("device_creation_denied",mknod("/data/raw",S_IFCHR|0600,makedev(90,0))==-1);
 check("no_inherited_fds",fcntl(3,F_GETFD)==-1&&errno==EBADF&&fcntl(2048,F_GETFD)==-1&&errno==EBADF);
 char block[1024];memset(block,'x',sizeof block);
 int fd=open("/data/large",O_WRONLY|O_CREAT,0600);int limit=0;
 if(fd>=0){for(int i=0;i<12;i++){if(write(fd,block,sizeof block)<0){limit=errno==EFBIG;break;}}close(fd);unlink("/data/large");}
 check("file_size_limit",limit);
 int full=0;
 for(int i=0;i<256;i++){char p[64];snprintf(p,sizeof p,"/data/f%03d",i);fd=open(p,O_WRONLY|O_CREAT,0600);if(fd<0){full=errno==ENOSPC;break;}ssize_t n=write(fd,block,sizeof block);int err=errno;close(fd);if(n<0){full=err==ENOSPC;break;}}
 check("bounded_data_stops_growth",full);
 return failed?1:0;
}
