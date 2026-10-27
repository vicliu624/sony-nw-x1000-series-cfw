#ifndef HB_STORE_HOST_FIXTURE
#error "Host fault-injection library only"
#endif
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static unsigned counter;
static int selected(const char *operation,const char *path) {
 const char *root=getenv("HB_TEST_ROOT"),*name=getenv("HB_TEST_OPERATION");
 const char *nth=getenv("HB_TEST_NTH");
 if(!root||!name||!nth||strcmp(name,operation))return 0;
 size_t n=strlen(root);
 if(strncmp(root,path,n)||(path[n]&&path[n]!='/'))return 0;
 return ++counter==(unsigned)strtoul(nth,0,10);
}
static int selected_fd(const char *operation,int fd) {
 char link[64],path[4096];snprintf(link,sizeof link,"/proc/self/fd/%d",fd);
 ssize_t n=readlink(link,path,sizeof path-1);if(n<0)return 0;path[n]=0;
 return selected(operation,path);
}
static int before(void) {
 const char *mode=getenv("HB_TEST_MODE");return mode&&!strcmp(mode,"before");
}
static void fault(void) {
 const char *mode=getenv("HB_TEST_MODE");
 if(mode&&!strcmp(mode,"exit"))_exit(90);
 errno=EIO;
}
int rename(const char *from,const char *to) {
 int (*real)(const char *,const char *)=dlsym(RTLD_NEXT,"rename");
 int hit=selected("rename",from);
 if(hit&&before()){fault();return -1;}
 int result=real(from,to);if(hit&&result==0){fault();return -1;}return result;
}
int unlink(const char *path) {
 int (*real)(const char *)=dlsym(RTLD_NEXT,"unlink");
 int hit=selected("unlink",path);
 if(hit&&before()){fault();return -1;}
 int result=real(path);if(hit&&result==0){fault();return -1;}return result;
}
int rmdir(const char *path) {
 int (*real)(const char *)=dlsym(RTLD_NEXT,"rmdir");
 int hit=selected("rmdir",path);
 if(hit&&before()){fault();return -1;}
 int result=real(path);if(hit&&result==0){fault();return -1;}return result;
}
int fsync(int fd) {
 int (*real)(int)=dlsym(RTLD_NEXT,"fsync");
 int hit=selected_fd("fsync",fd);
 if(hit&&before()){fault();return -1;}
 int result=real(fd);if(hit&&result==0){fault();return -1;}return result;
}
ssize_t write(int fd,const void *data,size_t size) {
 ssize_t (*real)(int,const void *,size_t)=dlsym(RTLD_NEXT,"write");
 int hit=selected_fd("write",fd);
 if(hit&&before()){fault();return -1;}
 ssize_t result=real(fd,data,size);if(hit&&result>=0){fault();return -1;}return result;
}
