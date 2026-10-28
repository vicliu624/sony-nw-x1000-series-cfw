#define _GNU_SOURCE
#include "../qqmusic/qqmusic_font.h"
#include "../qqmusic/qqmusic_workspace.h"
#include "../qqmusic/qqmusic_wifi.h"
#include "../qqmusic/qqmusic_asset.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/frontend.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../../store/target_abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern int sony_sscanf(const char *,const char *,...) __asm__("sscanf");
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
static volatile int stopped;
static unsigned short surface[HB_DISPLAY_PIXELS];
static char rows[19][39];static unsigned row;
static char mount_snapshot[65537];
#include "../../native/font.inc"
static void line(const char *text){if(row<19){size_t n=strlen(text);if(n>38)n=38;memcpy(rows[row],text,n);rows[row++][n]=0;}}
static void result(const char *name,int rc,int error){char text[80];sony_snprintf(text,sizeof(text),"%s RC %d ERRNO %d",name,rc,rc<0?error:0);line(text);}
static int main_help(const char *path,char **environment,char output[513]){
 int descriptors[2],flags,status=0,reaped=0;pid_t pid;unsigned elapsed=0;size_t used=0;
 output[0]=0;if(pipe(descriptors))return -1;
 flags=sony_fcntl(descriptors[0],F_GETFL,0);
 if(flags<0||sony_fcntl(descriptors[0],F_SETFL,flags|O_NONBLOCK)<0){close(descriptors[0]);close(descriptors[1]);return -1;}
 pid=fork();
 if(pid<0){close(descriptors[0]);close(descriptors[1]);return -1;}
 if(!pid){
  char *args[]={(char *)path,"--help",0};
  close(descriptors[0]);if(dup2(descriptors[1],1)<0||dup2(descriptors[1],2)<0)_exit(126);close(descriptors[1]);
  execve(args[0],args,environment);_exit(127);
 }
 close(descriptors[1]);
 while(elapsed<5000&&!stopped){
  ssize_t n=sony_read(descriptors[0],output+used,512-used);pid_t got;
  if(n>0)used+=(size_t)n;
  got=waitpid(pid,&status,WNOHANG);if(got==pid){reaped=1;break;}if(got<0&&errno!=EINTR)break;
  poll(0,0,10);elapsed+=10;
 }
 if(!reaped){kill(pid,SIGKILL);while(waitpid(pid,&status,0)<0&&errno==EINTR){}close(descriptors[0]);output[used]=0;return -2;}
 while(used<512){ssize_t n=sony_read(descriptors[0],output+used,512-used);if(n<=0)break;used+=(size_t)n;}
 output[used]=0;close(descriptors[0]);
 return WIFEXITED(status)?WEXITSTATUS(status):128+(WIFSIGNALED(status)?WTERMSIG(status):0);
}
static void observe(void){
 FILE *file;char text[2048],mount[1025],source[513],type[65],options[257];struct stat st;int rc,error;size_t used=0;
 struct qq_storage_policy policy={"/dev/mtdblock/2","vfat"};
 errno=0;rc=lstat("/contents/HOMEBREW/data/qqmusic",&st);error=errno;result("DATA",rc,error);
 if(!rc&&!S_ISDIR(st.st_mode))line("DATA IS NOT DIRECTORY");
 errno=0;rc=lstat("/contents/MUSIC",&st);error=errno;result("MUSIC",rc,error);
 file=fopen("/proc/self/mounts","r");
 if(!file){result("MOUNTS",-1,errno);return;}
 while(fgets(text,sizeof(text),file)){
  size_t n=strlen(text);if(n>sizeof(mount_snapshot)-1-used){used=0;break;}memcpy(mount_snapshot+used,text,n);used+=n;
  if(sony_sscanf(text,"%512s %1024s %64s %256s",source,mount,type,options)!=4)continue;
  if(!strcmp(mount,"/")){char root[80];sony_snprintf(root,sizeof(root),"ROOT %s %s",source,type);line(root);}
  if(!strcmp(mount,"/contents")){line("USER MOUNT SOURCE");line(source);line(type);line(options);}
 }
 if(ferror(file))used=0;
 fclose(file);
 result("TABLE REASON",qq_storage_mount_reason(&policy,mount_snapshot,used),0);
}
static void probe(char **environment){
 static const unsigned char hash[32]=QQ_FONT_SHA256;
 struct qq_storage_policy policy={"/dev/mtdblock/2","vfat"};struct qq_storage_plan plan;struct qq_volume volume;struct qq_workspace workspace;
 struct rlimit limit={0,0};struct qq_asset_mapping mapping={0};char output[513];uint64_t required;int rc,error;
 errno=0;rc=setrlimit(RLIMIT_CORE,&limit);error=errno;result("CORE",rc,error);
 errno=0;rc=main_help("/contents/HOMEBREW/apps/qqmusic/app",environment,output);error=errno;result("MAIN HELP",rc,error);
 if(rc&&output[0]){char clean[39];size_t i;for(i=0;i<38&&output[i];i++)clean[i]=output[i]>=32&&output[i]<127?output[i]:' ';clean[i]=0;line(clean);}
 /* Read-only observations only. No cnmgr init/fin/power/connect calls. */
 errno=0;rc=qq_wifi_ipc_guard();error=errno;result("WIFI IPC",rc,error);
 result("WIFI ROUTE",qq_wifi_route_ready()?0:-1,0);
 observe();memset(&plan,0,sizeof(plan));qq_volume_init(&volume);qq_workspace_init(&workspace);
 errno=0;rc=qq_volume_open(&volume,&policy,"/contents/HOMEBREW/data/qqmusic",&plan,&required);error=errno;result("VOLUME",rc,error);result("VOL STEP",(int)qq_volume_failure_step(),0);qq_volume_close(&volume);
 errno=0;rc=qq_workspace_open(&workspace,&policy,&stopped);error=errno;result("WORKSPACE",rc,error);qq_workspace_close(&workspace);
 qq_volume_init(&volume);errno=0;
 rc=qq_volume_open(&volume,&policy,"/contents/HOMEBREW/apps/qqmusic/resources",&plan,&required);error=errno;result("RESOURCE VOL",rc,error);
 if(!rc){errno=0;rc=qq_asset_map(&volume,&plan,QQ_FONT_NAME,QQ_FONT_BYTES,hash,&mapping);error=errno;result("FONT MAP",rc,error);qq_asset_unmap(&mapping);}
 qq_volume_close(&volume);
}
static void rect(int x,int y,int w,int h,unsigned short color){int i,j;for(j=y;j<y+h&&j<432;j++)for(i=x;i<x+w&&i<240;i++)surface[j*240+i]=color;}
static void text(int x,int y,const char *s,unsigned scale,unsigned short color){
 for(;*s&&x<234;s++,x+=(int)(6*scale)){unsigned char c=(unsigned char)*s;int g,j,i;if(c>='a'&&c<='z')c-=32;g=c>='0'&&c<='9'?c-'0':c>='A'&&c<='Z'?c-'A'+10:-1;
  if(g>=0){for(j=0;j<7;j++)for(i=0;i<5;i++)if(glyph[g][j]&(1<<(4-i)))rect(x+i*(int)scale,y+j*(int)scale,(int)scale,(int)scale,color);}
  else if(c!=' ')rect(x,y+3*(int)scale,3*(int)scale,(int)scale,color);
 }
}
int main(int argc,char **argv,char **environment){
 struct hb_devices devices;unsigned i;int pressed=0;
 if(argc==2&&!strcmp(argv[1],"--help")){static const char help[]="QQ Music startup checker: no login; RAM-only results; user-volume workspace lock only.\n";return write(1,help,sizeof(help)-1)==sizeof(help)-1?0:1;}
 if(hb_stop_signals_install(&stopped))return 2;
 if(hb_devices_open(&devices,surface,HB_DISPLAY_PIXELS,&stopped))return 2;
 rect(0,0,240,432,0x0843);text(10,16,"QQ START CHECK 5",2,0xffff);text(10,60,"CHECKING NO LOGIN",1,0xffe0);hb_devices_present(&devices);
 probe(environment);
 rect(0,0,240,432,0x0843);text(10,16,"QQ START CHECK 5",2,0xffff);
 for(i=0;i<row;i++)text(6,54+(int)i*17,rows[i],1,0xffff);
 text(8,404,"TAP TO RETURN",1,0xffe0);hb_devices_present(&devices);
 while(!stopped&&!devices.failed){unsigned char packet[11];struct hb_touch touch;int got=hb_devices_next_touch(&devices,packet,50);if(got<0)break;hb_devices_flush(&devices);if(got){hb_touch_decode(packet,&touch);if(touch.down)pressed=1;else if(pressed)break;}}
 return hb_devices_close(&devices)?2:0;
}
