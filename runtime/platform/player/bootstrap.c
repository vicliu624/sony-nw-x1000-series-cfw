/* Optional C exec layer, not installed by SDK/build. AppList identity stays put. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#ifdef XW_PLAYER_ONCE_TARGET
#include <sys/mount.h>
#ifndef XW_PLAYER_ONCE_SOURCE
#error Explicit mounted wrapper source is required
#endif
static int same_file_bytes(const char *a,const char *b){
 FILE *first=fopen(a,"rb"),*second=fopen(b,"rb");
 if(!first||!second){if(first)fclose(first);if(second)fclose(second);return 0;}
 unsigned char x[512],y[512];size_t n,m;int equal=1;
 do{n=fread(x,1,sizeof x,first);m=fread(y,1,sizeof y,second);if(n!=m||memcmp(x,y,n)){equal=0;break;}}while(n);
 if(ferror(first)||ferror(second))equal=0;fclose(first);fclose(second);return equal;
}
static int detach_own_overlay(void){
 if(!same_file_bytes("/proc/self/exe",XW_PLAYER_ONCE_SOURCE))return -1;
 FILE *mounts=fopen("/proc/mounts","r");if(!mounts)return -1;
 char line[512],match[160];snprintf(match,sizeof match," %s ",XW_PLAYER_ONCE_TARGET);int found=0;
 while(fgets(line,sizeof line,mounts))if(strstr(line,match)){found=1;break;}
 fclose(mounts);return found?umount2(XW_PLAYER_ONCE_TARGET,MNT_DETACH):-1;
}
#endif
#ifdef XW_PLAYER_STARTUP_DIRECTORY
#include "startup_delivery.h"
#include <fcntl.h>
#if !defined(XW_PLAYER_STARTUP_NONCE) || !defined(XW_PLAYER_FALLBACK) || !defined(XW_PLAYER_STARTUP_GENERATION) || !defined(XW_PLAYER_STARTUP_GRANTS)
#error Explicit startup nonce and original fallback payload are required
#endif
extern int bootstrap_fcntl(int,int,...) __asm__("fcntl");
static int startup_channel(void){
 int fd=xw_player_startup_connect(XW_PLAYER_STARTUP_DIRECTORY,XW_PLAYER_STARTUP_NONCE,XW_PLAYER_STARTUP_GENERATION,XW_PLAYER_STARTUP_GRANTS,1000);
 if(fd<0)return -1;
 if(fd<3){int replacement=bootstrap_fcntl(fd,F_DUPFD,3);close(fd);if(replacement<0)return -1;fd=replacement;}
 char number[24],epoch[24],grants[12];snprintf(number,sizeof number,"%d",fd);
 snprintf(epoch,sizeof epoch,"%llu",(unsigned long long)XW_PLAYER_STARTUP_GENERATION);
 snprintf(grants,sizeof grants,"%u",(unsigned)XW_PLAYER_STARTUP_GRANTS);
 if(setenv("X1000_PLAYER_INHERITED","1",1)||setenv("X1000_PLAYER_DELIVERY_FD",number,1)||
    setenv("X1000_PLAYER_GENERATION",epoch,1)||setenv("X1000_PLAYER_GRANTS",grants,1)||bootstrap_fcntl(fd,F_SETFD,0)){
  close(fd);unsetenv("X1000_PLAYER_INHERITED");unsetenv("X1000_PLAYER_DELIVERY_FD");unsetenv("X1000_PLAYER_GENERATION");unsetenv("X1000_PLAYER_GRANTS");return -1;
 }
 return fd;
}
#endif
#ifndef XW_PLAYER_PAYLOAD
#define XW_PLAYER_PAYLOAD "/usr/local/lib/x1000-player/SpiderApp"
#endif
#ifndef XW_PLAYER_LIBRARY
#define XW_PLAYER_LIBRARY "/usr/local/lib/libx1000-player.so"
#endif
extern char **environ;
#if defined(XW_PLAYER_SYSTEM_PRELOAD) && defined(XW_PLAYER_STARTUP_DIRECTORY)
#error System preload and one-shot startup delivery are separate profiles
#endif
int main(int argc,char **argv){
 (void)argc;const char *enabled=getenv("X1000_PLAYER_SERVICE"),*payload=XW_PLAYER_PAYLOAD;
#ifdef XW_PLAYER_SYSTEM_PRELOAD
 /* Install the ABI bridge, not a controller grant. A later owner-authorized
  * Settings action must create its own session. Never adopt inherited one-shot
  * authorization variables in this long-lived system profile. */
 enabled="1";
 if(unsetenv("X1000_PLAYER_INHERITED")||unsetenv("X1000_PLAYER_DELIVERY_FD")||
    unsetenv("X1000_PLAYER_GENERATION")||unsetenv("X1000_PLAYER_GRANTS"))return 126;
#endif
#ifdef XW_PLAYER_ONCE_TARGET
 /* Remove only this explicitly configured, byte-matched transient overlay.
  * Lazy detach permits this wrapper's existing executable mapping to finish;
  * future manager launches resolve the original filesystem entry again. */
 if(detach_own_overlay()){perror("player bootstrap: detach own overlay");return 126;}
#endif
#ifdef XW_PLAYER_STARTUP_DIRECTORY
 /* Explicit temporary validation profile only. No manager environment change
  * or permanent listener is needed. Keep a separately retained original path. */
 int delivery=-1;
 if(!access(XW_PLAYER_LIBRARY,R_OK)&&!access(payload,X_OK))delivery=startup_channel();
 if(delivery<0){payload=XW_PLAYER_FALLBACK;enabled="0";}else enabled="1";
#endif
 if(enabled&&!strcmp(enabled,"1")&&!access(XW_PLAYER_LIBRARY,R_OK)){
  const char *previous=getenv("LD_PRELOAD");size_t n=strlen(XW_PLAYER_LIBRARY),m=previous?strlen(previous):0;
  if(m<=SIZE_MAX-n-2){
   char *value=malloc(n+m+2);
   if(value){
    memcpy(value,XW_PLAYER_LIBRARY,n);if(m){value[n++]=' ';memcpy(value+n,previous,m);}value[n+m]=0;
    (void)setenv("LD_PRELOAD",value,1);free(value);
   }
  }
 }
 /* exec preserves PID, working directory, argv and non-CLOEXEC descriptors.
  * The intended non-setid payload retains credentials. Its basename stays
  * SpiderApp so kernel process-name lookup is kept. */
#ifdef XW_PLAYER_ARGV0
 if(argc<1||!argv)return 126;
 argv[0]=XW_PLAYER_ARGV0;
#endif
 execve(payload,argv,environ);
 perror("player bootstrap: exec payload");return 127;
}
