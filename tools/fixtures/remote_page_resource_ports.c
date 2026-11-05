/* Readiness port test in a disposable, device-free ARM guest only. */
#define _DEFAULT_SOURCE
#include "remote_native_page_profile.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/stat.h>
extern int wr_view_resource_ready(void);
extern int stock_fcntl(int,int,...) __asm__("fcntl");
int xw_player_remote_view_image_valid(void){return 1;} /* Not called by resource readiness. */
static unsigned char original[XW_REMOTE_RESOURCE_BYTES];
static int fds(void){int count=0;for(int fd=3;fd<64;fd++)if(stock_fcntl(fd,F_GETFD)>=0)count++;return count;}
static void write_resource(unsigned bytes){
 int fd=open(XW_REMOTE_RESOURCE_PATH,O_WRONLY|O_CREAT|O_TRUNC,0644);assert(fd>=0);
 assert(bytes<=sizeof original&&write(fd,original,bytes)==(ssize_t)bytes&&!close(fd));
}
static void check(int expected){
 int before=fds();errno=77;assert(wr_view_resource_ready()==expected&&errno==77);assert(fds()==before);
}
int main(void){
 int fd=open("/resource-good.bin",O_RDONLY);assert(fd>=0);
 assert(read(fd,original,sizeof original)==sizeof original&&!close(fd));
 check(1);
 fd=open(XW_REMOTE_RESOURCE_PATH,O_WRONLY);assert(fd>=0);unsigned char changed=original[0]^1;
 assert(write(fd,&changed,1)==1&&!close(fd));check(0);
 write_resource(sizeof original-1);check(0);
 write_resource(sizeof original);fd=open(XW_REMOTE_RESOURCE_PATH,O_WRONLY|O_APPEND);assert(fd>=0);
 assert(write(fd,"x",1)==1&&!close(fd));check(0);
 assert(!unlink(XW_REMOTE_RESOURCE_PATH));check(0);
 assert(!symlink("/resource-good.bin",XW_REMOTE_RESOURCE_PATH));check(0);assert(!unlink(XW_REMOTE_RESOURCE_PATH));
 assert(!mkdir(XW_REMOTE_RESOURCE_PATH,0700));check(0);assert(!rmdir(XW_REMOTE_RESOURCE_PATH));
 assert(!link("/resource-good.bin",XW_REMOTE_RESOURCE_PATH));check(0);assert(!unlink(XW_REMOTE_RESOURCE_PATH));
 write_resource(sizeof original);
 for(unsigned i=0;i<20;i++)check(1);
 puts("REMOTE_PAGE_RESOURCE_PORTS_PASS");return 0;
}
