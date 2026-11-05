#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <fcntl.h>
extern int payload_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern int payload_fcntl(int,int,...) __asm__("fcntl");
/* This query has no time structure; bind the original scalar ABI explicitly. */
extern int stock_prctl(int,...) __asm__("prctl");
int main(int argc,char **argv){
 assert(argc==4&&!strcmp(argv[0],getenv("TEST_ARG0"))&&!strcmp(argv[1],"--native")&&!strcmp(argv[2],"argument with spaces")&&!strcmp(argv[3],"last"));
 assert(getpid()==(int)strtol(getenv("TEST_PID"),0,10));
 if(!strcmp(getenv("TEST_SYSTEM"),"1")){
  assert(!getenv("X1000_PLAYER_INHERITED")&&!getenv("X1000_PLAYER_DELIVERY_FD")&&
         !getenv("X1000_PLAYER_GENERATION")&&!getenv("X1000_PLAYER_GRANTS"));
 }
 if(!strcmp(getenv("TEST_STARTUP"),"1")){
  assert(!strcmp(getenv("X1000_PLAYER_INHERITED"),"1")&&!strcmp(getenv("X1000_PLAYER_GENERATION"),"23")&&!strcmp(getenv("X1000_PLAYER_GRANTS"),"1"));
  int channel=(int)strtol(getenv("X1000_PLAYER_DELIVERY_FD"),0,10),type=0;socklen_t size=sizeof type;
  assert(channel>=3&&!payload_getsockopt(channel,SOL_SOCKET,SO_TYPE,&type,&size)&&type==SOCK_DGRAM);
  int flags=payload_fcntl(channel,F_GETFD);assert(flags>=0);
  assert(!!(flags&FD_CLOEXEC)==!strcmp(getenv("TEST_MANAGED"),"1"));
 }
 char name[32]={0};assert(!stock_prctl(PR_GET_NAME,name,0,0,0)&&!strcmp(name,"SpiderApp"));
 char cwd[64];assert(getcwd(cwd,sizeof cwd)&&!strcmp(cwd,"/"));assert(!strcmp(getenv("KEEP_ENV"),"unchanged"));
 char inherited[16]={0};int fd=(int)strtol(getenv("TEST_FD"),0,10);assert(read(fd,inherited,10)==10&&!strcmp(inherited,"manager-fd"));close(fd);
 int service=!strcmp(getenv("TEST_SERVICE"),"1"),old=!strcmp(getenv("TEST_OLD"),"1");
 int (*resolved)(void)=(int (*)(void))dlsym(RTLD_DEFAULT,"xw_player_host_pid_resolved");
 int (*marker)(void)=(int (*)(void))dlsym(RTLD_DEFAULT,"player_original_preload_marker");
 assert(!!resolved==service&&!!marker==old);if(resolved)assert(resolved());if(marker)assert(marker()==17);
 const char *preload=getenv("LD_PRELOAD");
 if(service){const char *expected=getenv("TEST_EXPECT_PRELOAD");assert(preload&&!strcmp(preload,expected?expected:old?"/lib/libx1000-player.so /lib/original-marker.so":"/lib/libx1000-player.so"));}
 else if(old)assert(preload&&!strcmp(preload,"/lib/original-marker.so"));else assert(!preload);
 int (*anchor_ready)(void)=(int (*)(void))dlsym(RTLD_DEFAULT,"xw_player_host_anchor_ready");
 if(service)assert(anchor_ready&&!anchor_ready());
 puts("BOOTSTRAP_PAYLOAD_PASS: PID argv name cwd environment and preload verified");fflush(stdout);return 0;
}
