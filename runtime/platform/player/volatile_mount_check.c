/* Explicit temporary-text check, not an installer or general mount utility. */
#define _POSIX_C_SOURCE 200809L
#include <sys/mount.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
static int content(const char *path,const char *expected){
 FILE *f=fopen(path,"rb");if(!f)return 0;char bytes[32]={0};size_t n=fread(bytes,1,sizeof bytes,f);int bad=ferror(f);fclose(f);
 return !bad&&n==strlen(expected)&&!memcmp(bytes,expected,n);
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Explicit check: --check dedicated player-sdk-live-N/bind-check; requires SOURCE and ORIGINAL text fixtures. Tests direct file bind and normal/lazy unmount only.");return 0;}
 if(argc!=3||strcmp(argv[1],"--check"))return 64;
 static const char prefix[]="/contents/HOMEBREW/data/player-sdk-live-";
 if(strncmp(argv[2],prefix,sizeof prefix-1)||strlen(argv[2])>180)return 64;
 const char *p=argv[2]+sizeof prefix-1,*first=p;while(*p>='0'&&*p<='9')p++;
 if(p==first||strcmp(p,"/bind-check"))return 64;
 char source[220],target[220];snprintf(source,sizeof source,"%s/source",argv[2]);snprintf(target,sizeof target,"%s/target",argv[2]);
 if(!content(source,"SOURCE\n")||!content(target,"ORIGINAL\n"))return 65;
 for(unsigned lazy=0;lazy<2;lazy++){
  if(mount(source,target,0,MS_BIND,0)){printf("DIRECT_BIND_FAILED errno=%d\n",errno);return 66;}
  int same=content(target,"SOURCE\n");
  if(umount2(target,lazy?MNT_DETACH:0)){printf("UNMOUNT_FAILED mode=%u errno=%d\n",lazy,errno);return 67;}
  if(!same||!content(target,"ORIGINAL\n"))return 68;
  printf("DIRECT_BIND_RESTORE_PASS lazy=%u\n",lazy);
 }
 return 0;
}
