#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <string.h>
#include <errno.h>
#include <poll.h>
#include "../../runtime/platform/player/startup_delivery.h"
extern char **environ;
static int equal_files(const char *a,const char *b){
 FILE *x=fopen(a,"rb"),*y=fopen(b,"rb");if(!x||!y)return 0;
 unsigned char first[512],second[512];size_t n,m;int same=1;
 do{n=fread(first,1,sizeof first,x);m=fread(second,1,sizeof second,y);if(n!=m||memcmp(first,second,n)){same=0;break;}}while(n);
 if(ferror(x)||ferror(y))same=0;fclose(x);fclose(y);return same;
}
static int copy_file(const char *a,const char *b){
 FILE *x=fopen(a,"rb"),*y=fopen(b,"wb");if(!x||!y)return 0;
 unsigned char data[512];size_t n;int ok=1;
 while((n=fread(data,1,sizeof data,x)))if(fwrite(data,1,n,y)!=n){ok=0;break;}
 if(ferror(x))ok=0;fclose(x);if(fclose(y))ok=0;
 return ok&&chmod(b,0755)==0;
}
int main(void){
 if(mount("proc","/proc","proc",0,0))return 1;
 if(mkdir("/tmp",0700)&&errno!=EEXIST)return 10;
 for(unsigned i=0;i<10;i++){
  int rendezvous=-1;
  if(i==7){if(mkdir("/tmp/x1000-player-bootstrap",0700))return 7;rendezvous=xw_player_startup_listen("/tmp/x1000-player-bootstrap");if(rendezvous<0)return 7;}
  if(i==5){
   if(mount("tmpfs","/bind","tmpfs",0,0)||!copy_file("/bin/SpiderApp","/bind/wrapper")||!copy_file("/payload/SpiderApp","/bind/SpiderApp")){puts("PLAYER_BIND_FILESYSTEM_SETUP_FAILED");fflush(stdout);return 5;}
   if(!equal_files("/bind/SpiderApp","/payload/SpiderApp")){puts("PLAYER_BIND_BASELINE_DIFFERENT");fflush(stdout);return 5;}
   if(mount("/bind/wrapper","/bind/SpiderApp",0,MS_BIND,0)){printf("PLAYER_BIND_FAILED errno=%d\n",errno);fflush(stdout);return 5;}
  }
  if(i==8&&(!copy_file("/once/SpiderApp","/bind/once-wrapper")||mount("/bind/once-wrapper","/bind/SpiderApp",0,MS_BIND,0)))return 11;
  int child=fork();if(child<0)return 2;
  if(!child){
   if(rendezvous>=0)close(rendezvous);
   char pid[32];snprintf(pid,sizeof pid,"%ld",(long)getpid());setenv("TEST_PID",pid,1);setenv("KEEP_ENV","unchanged",1);setenv("LD_LIBRARY_PATH","/lib",1);
   int inherited[2];if(pipe(inherited)||write(inherited[1],"manager-fd",10)!=10)_exit(125);close(inherited[1]);
   char fd[32];snprintf(fd,sizeof fd,"%d",inherited[0]);setenv("TEST_FD",fd,1);
   char *arg0=i==2?"/usr/local/bin/SpiderApp":"SpiderApp";setenv("TEST_ARG0",arg0,1);
   if(i==0)unsetenv("X1000_PLAYER_SERVICE");else setenv("X1000_PLAYER_SERVICE",i==3||i==9?"0":"1",1);
   if(i==9){setenv("X1000_PLAYER_INHERITED","1",1);setenv("X1000_PLAYER_DELIVERY_FD","3",1);setenv("X1000_PLAYER_GENERATION","23",1);setenv("X1000_PLAYER_GRANTS","7",1);}
   setenv("TEST_SYSTEM",i==9?"1":"0",1);
   setenv("TEST_SERVICE",i==1||i==2||i==5||i==7||i==8||i==9?"1":"0",1);setenv("TEST_OLD",i>=2?"1":"0",1);
   setenv("TEST_STARTUP",i==7?"1":"0",1);
#ifdef HB_TEST_MANAGED
   setenv("TEST_MANAGED","1",1);
#else
   setenv("TEST_MANAGED","0",1);
#endif
   if(i>=2)setenv("LD_PRELOAD","/lib/original-marker.so",1);else unsetenv("LD_PRELOAD");
#ifdef XW_LAYOUT_SYSTEM
   if(i==9)setenv("TEST_EXPECT_PRELOAD","/usr/local/lib/libx1000-player.so /lib/original-marker.so",1);
#endif
   char *args[]={i==9?"/usr/local/libexec/x1000-player-start":arg0,"--native","argument with spaces","last",0};
   execve(i==9?"/system/SpiderApp":i==8?"/bind/SpiderApp":i>=6?"/startup/SpiderApp":i==5?"/bind/SpiderApp":i==4?"/missing/SpiderApp":"/bin/SpiderApp",args,environ);_exit(127);
  }
  if(i==7){
   int accepted=1;for(unsigned attempts=0;attempts<2000&&accepted==1;attempts++){accepted=xw_player_startup_accept(rendezvous,"/tmp/x1000-player-bootstrap","0123456789abcdef0123456789abcdef",23,1);if(accepted==1)poll(0,0,1);}
   if(accepted)return 8;close(rendezvous);
  }
  int status=0;if(waitpid(child,&status,0)!=child)return 3;
  printf("PLAYER_BOOTSTRAP_CASE=%u STATUS=%d\n",i,status);fflush(stdout);if(status)return 4;
  if(i==5){if(umount("/bind/SpiderApp")||!equal_files("/bind/SpiderApp","/payload/SpiderApp"))return 6;puts("PLAYER_VOLATILE_BIND_RESTORED");}
  if(i==7){if(unlink("/tmp/x1000-player-bootstrap/controller.sock")||rmdir("/tmp/x1000-player-bootstrap"))return 9;puts("PLAYER_BOOTSTRAP_RENDEZVOUS_PASS");}
  if(i==8){if(!equal_files("/bind/SpiderApp","/payload/SpiderApp"))return 12;puts("PLAYER_BOOTSTRAP_SELF_DETACH_PASS");}
 }
 puts("PLAYER_BOOTSTRAP_SYSTEM_PASS");fflush(stdout);for(;;)pause();
}
