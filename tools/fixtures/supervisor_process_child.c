/* Host-only child model; no player, files, driver or radio operations. */
#define _DEFAULT_SOURCE
#include <assert.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
int main(int argc,char **argv){
 assert(argc==8&&!strcmp(argv[1],"--delivery-fd")&&!strcmp(argv[4],"--stop-fd")&&!strcmp(argv[6],"--charger-confirmed")&&!strcmp(argv[7],"--exclusive-radio-confirmed"));
 int fd=atoi(argv[2]),mode=atoi(argv[3]),stop=atoi(argv[5]);assert(fd>=3&&stop>=3&&stop!=fd);
 assert(!getenv("LD_PRELOAD")&&!getenv("X1000_PLAYER_INHERITED"));
 char cwd[16];assert(getcwd(cwd,sizeof cwd)&&!strcmp(cwd,"/"));
 unsigned inherited=0;for(int i=3;i<128;i++)if(fcntl(i,F_GETFD)>=0){assert(i==fd||i==stop);inherited++;}assert(inherited==2);
 if(mode==4){usleep(50000);return 9;}
 char token=0;for(unsigned i=0;i<1000;i++){
  ssize_t n=read(fd,&token,1);if(n==1)break;
  assert(n<0&&(errno==EAGAIN||errno==EINTR));usleep(1000);
 }
 assert(token=='x');char data[256];memset(data,'L',sizeof data);
 if(mode==1){char command;assert(read(stop,&command,1)==1&&command=='S');}
 for(unsigned i=0;i<4;i++)assert(write(1,data,sizeof data)==sizeof data);
 return mode==2?7:0;
}
