/* Test-only link wrappers. Never part of a candidate. */
#include <unistd.h>
#include <errno.h>
extern ssize_t __real_write(int,const void *,size_t);
extern int __real_fsync(int);
extern int __real_close(int);
static int mode,nth,seen;
void hb_download_test_fault(int kind,int target){mode=kind;nth=target;seen=0;}
ssize_t __wrap_write(int fd,const void *data,size_t bytes){
 if(mode>=1&&mode<=3&&++seen==nth){
  if(mode==3)return __real_write(fd,data,bytes?1:0);
  if(mode==2){ssize_t n=__real_write(fd,data,bytes);if(n<0)return n;}
  errno=EIO;return -1;
 }return __real_write(fd,data,bytes);
}
int __wrap_fsync(int fd){
 if(mode==4&&++seen==nth){errno=EIO;return -1;}
 return __real_fsync(fd);
}
int __wrap_close(int fd){
 int result=__real_close(fd);
 if(mode==5&&++seen==nth&&!result){errno=EIO;return -1;}
 return result;
}
