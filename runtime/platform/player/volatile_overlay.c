/* Private per-attempt activator. No generic paths, boot edits or flash writes. */
#define _GNU_SOURCE
#include "../../native/sha256.h"
#include <sys/mount.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#ifndef XW_LIVE_STAGE
#error Compile a reviewed per-attempt staging profile
#endif
static const char *root="/usr/local/bin/SpiderApp";
static int digest(const char *path,const char *expected,unsigned long limit){
 int fd=open(path,O_RDONLY|O_NOFOLLOW);if(fd<0)return 0;
 struct hb_sha256 hash;unsigned char data[4096],result[32];unsigned long total=0;int okay=1;hb_sha256_init(&hash);
 for(;;){ssize_t n=read(fd,data,sizeof data);if(n<0){okay=0;break;}if(!n)break;
  if((unsigned long)n>limit-total){okay=0;break;}total+=(unsigned long)n;hb_sha256_update(&hash,data,(size_t)n);
 }
 close(fd);if(!okay||total!=limit)return 0;hb_sha256_final(&hash,result);
 const char digits[]="0123456789abcdef";
 for(unsigned i=0;i<32;i++)if(expected[i*2]!=digits[result[i]>>4]||expected[i*2+1]!=digits[result[i]&15])return 0;
 return 1;
}
static int directory(const char *path){int fd=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return 0;close(fd);return 1;}
static int filesystems(void){
 FILE *f=fopen("/proc/mounts","r");if(!f)return 0;char line[512];unsigned flags=0;
 while(fgets(line,sizeof line,f)){
  if(strstr(line,"/dev/root / ext2 ro,"))flags|=1;
  if(strstr(line,"/dev/mtdblock/2 /contents vfat rw,"))flags|=2;
 }
 fclose(f);return flags==3;
}
static int target_mounted(void){
 FILE *f=fopen("/proc/mounts","r");if(!f)return -1;char line[512];int found=0;
 while(fgets(line,sizeof line,f))if(strstr(line," /usr/local/bin/SpiderApp ")){found=1;break;}
 fclose(f);return found;
}
static int originals(void){return digest(root,XW_LIVE_BASE_SHA,XW_LIVE_BASE_BYTES);}
static int wrapper(void){return digest(root,XW_LIVE_WRAPPER_SHA,XW_LIVE_WRAPPER_BYTES);}
static int preflight(void){
 const char *dirs[]={"/contents","/contents/HOMEBREW","/contents/HOMEBREW/data",XW_LIVE_STAGE,XW_LIVE_STAGE "/original",XW_LIVE_STAGE "/sdk",XW_LIVE_STAGE "/wrapper"};
 for(unsigned i=0;i<sizeof dirs/sizeof dirs[0];i++)if(!directory(dirs[i]))return 0;
 return filesystems()&&target_mounted()==0&&originals()&&
  digest(XW_LIVE_STAGE "/original/SpiderApp",XW_LIVE_BASE_SHA,XW_LIVE_BASE_BYTES)&&
  digest(XW_LIVE_STAGE "/sdk/SpiderApp",XW_LIVE_PAYLOAD_SHA,XW_LIVE_PAYLOAD_BYTES)&&
  digest(XW_LIVE_STAGE "/sdk/libx1000-player.so",XW_LIVE_LIBRARY_SHA,XW_LIVE_LIBRARY_BYTES)&&
  digest(XW_LIVE_STAGE "/wrapper/SpiderApp",XW_LIVE_WRAPPER_SHA,XW_LIVE_WRAPPER_BYTES);
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Private one-attempt overlay controller: --status / --check / --activate / --restore. Pinned paths and SHA256. No flash writes.");return 0;}
 if(argc!=2)return 64;
 if(!strcmp(argv[1],"--status")){
  if(originals()&&target_mounted()==0){puts("ROOT_ORIGINAL_NO_OVERLAY");return 0;}
  if(wrapper()&&target_mounted()==1){puts("REVIEWED_OVERLAY_PRESENT");return 0;}
  puts("UNRECOGNIZED_ROOT_STATE");return 65;
 }
 if(!strcmp(argv[1],"--restore")){
  if(originals()&&target_mounted()==0){puts("ROOT_ALREADY_ORIGINAL");return 0;}
  if(!wrapper()||target_mounted()!=1)return 65;
  if(umount2(root,MNT_DETACH)||!originals()||target_mounted()!=0)return 66;
  puts("ROOT_OVERLAY_REMOVED");return 0;
 }
 if(strcmp(argv[1],"--check")&&strcmp(argv[1],"--activate"))return 64;
 if(!preflight()){puts("LIVE_START_PREFLIGHT_REFUSED");return 67;}
 if(!strcmp(argv[1],"--check")){puts("LIVE_START_PREFLIGHT_PASS");return 0;}
 if(mount(XW_LIVE_STAGE "/wrapper/SpiderApp",root,0,MS_BIND,0)){perror("bind reviewed wrapper");return 68;}
 if(!wrapper()||target_mounted()!=1){umount2(root,MNT_DETACH);return 69;}
 puts("PLAYER_ONCE_OVERLAY_READY");return 0;
}
