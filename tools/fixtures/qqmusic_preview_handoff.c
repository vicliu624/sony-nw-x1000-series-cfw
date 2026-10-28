#define _XOPEN_SOURCE 700
#include "../../runtime/apps/qqmusic/qqmusic_preview_handoff.h"
#include "../../runtime/native/sha256.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <unistd.h>
#include <errno.h>
static const char *base;static unsigned role,bad_parent,spider_live,sound_live,reused;static unsigned reads;
static char mapped[4096];
static const char *map(const char *name){assert(snprintf(mapped,sizeof(mapped),"%s%s",base,name)>0);return mapped;}
extern int __real_open(const char *,int,...);
extern DIR *__real_opendir(const char *);
extern int __real_lstat(const char *,void *);
extern int __real___lxstat64(int,const char *,void *);
int __wrap_open(const char *name,int flags,...){assert((flags&O_ACCMODE)==O_RDONLY);assert(strncmp(name,"/dev/",5));reads++;return __real_open(map(name),flags);}
int __wrap_open64(const char *name,int flags,...){return __wrap_open(name,flags);}
DIR *__wrap_opendir(const char *name){return __real_opendir(map(name));}
#ifndef HB_STORE_SONY_LIBC
int __wrap_lstat(const char *name,void *out){return __real_lstat(map(name),out);}
#endif
int __wrap___lxstat64(int version,const char *name,void *out){return __real___lxstat64(version,map(name),out);}
pid_t __wrap_getpid(void){return 100;}
pid_t __wrap_getppid(void){return 101;}
ssize_t __wrap_readlink(const char *name,char *out,size_t cap){
 const char *value=0;unsigned pid;char expected[96];
 for(pid=100;pid<=106;pid++){
  assert(snprintf(expected,sizeof(expected),"/proc/%u/exe",pid)>0);if(strcmp(name,expected))continue;
  if(pid==100)value=role?"/contents/HOMEBREW/apps/qqmusic/audio-helper":"/contents/HOMEBREW/apps/qqmusic/app";
  else if(role&&pid==101)value="/contents/HOMEBREW/apps/qqmusic/app";
  else if(pid==101+role)value=bad_parent?"/contents/HOMEBREW/apps/terminal/app":"/contents/HOMEBREW/launcher/app";
  else if(pid<105+role)value="/usr/local/bin/appproxy";
  else value="/usr/local/bin/sysmgrd";
 }
 if(!strcmp(name,"/proc/300/exe"))value=spider_live?"/usr/local/bin/SpiderApp":"/bin/busybox";
 if(!strcmp(name,"/proc/300/fd/3"))value=sound_live?"/dev/sound/dsp":"/dev/null";
 if(!value){errno=ENOENT;return -1;}
 {size_t n=strlen(value);if(n>cap)n=cap;memcpy(out,value,n);return (ssize_t)n;}
}
static void directory(const char *suffix){char path[4096];assert(snprintf(path,sizeof(path),"%s%s",base,suffix)>0);assert(!mkdir(path,0700)||errno==EEXIST);}
static void file(const char *suffix,const void *data,size_t bytes){char path[4096];FILE *f;assert(snprintf(path,sizeof(path),"%s%s",base,suffix)>0);f=fopen(path,"wb");assert(f&&fwrite(data,1,bytes,f)==bytes&&!fclose(f));}
static void statfile(unsigned pid,unsigned parent){
 char suffix[96],text[2048];size_t used;unsigned field;
 assert(snprintf(suffix,sizeof(suffix),"/proc/%u/stat",pid)>0);used=(size_t)snprintf(text,sizeof(text),"%u (test ) name) S %u",pid,parent);
 for(field=5;field<22;field++)used+=(size_t)snprintf(text+used,sizeof(text)-used," 0");
 used+=(size_t)snprintf(text+used,sizeof(text)-used," %u 4096 0\n",1000+pid+(reused&&pid==101?1:0));file(suffix,text,used);
}
static void processes(void){
 unsigned pid;char suffix[96];
 for(pid=100;pid<=106;pid++){assert(snprintf(suffix,sizeof(suffix),"/proc/%u",pid)>0);directory(suffix);assert(snprintf(suffix,sizeof(suffix),"/proc/%u/fd",pid)>0);directory(suffix);statfile(pid,pid==105+role?1:pid+1);}
 directory("/proc/300");directory("/proc/300/fd");statfile(300,1);file("/proc/300/fd/3","",0);
}
static void registration(unsigned duplicate){static const char line[]="0x00030001 * /contents/HOMEBREW/launcher/app --native\n";char text[256];size_t n=sizeof(line)-1;memcpy(text,line,n);if(duplicate){memcpy(text+n,line,n);n*=2;}file("/etc/AppList.conf",text,n);}
static void identity(struct qq_preview_image *image,const unsigned char *data,size_t n){struct hb_sha256 hash;image->bytes=n;hb_sha256_init(&hash);hb_sha256_update(&hash,data,(unsigned)n);hb_sha256_final(&hash,image->sha256);}
int main(int argc,char **argv){
 struct qq_preview_handoff_policy policy;struct qq_preview_handoff_receipt receipt;unsigned char *spider;unsigned i,parent;uint64_t birth;unsigned before;
 assert(argc==2);base=argv[1];directory("/proc");directory("/etc");directory("/usr");directory("/usr/local");directory("/usr/local/bin");directory("/contents");directory("/contents/HOMEBREW");directory("/contents/HOMEBREW/launcher");
 spider=calloc(1,0x4ce1c4);assert(spider);memcpy(spider+0x4ce1c0,"\x01\x30\xa0\xe3",4);identity(&policy.spider,spider,0x4ce1c4);file("/usr/local/bin/SpiderApp",spider,0x4ce1c4);
 identity(&policy.launcher,(const unsigned char *)"launcher",8);identity(&policy.proxy,(const unsigned char *)"proxy",5);identity(&policy.manager,(const unsigned char *)"manager",7);
 file("/contents/HOMEBREW/launcher/app","launcher",8);file("/usr/local/bin/appproxy","proxy",5);file("/usr/local/bin/sysmgrd","manager",7);registration(0);processes();
 before=reads;assert(qq_preview_handoff_check(0,0,&receipt)<0&&reads==before);{struct qq_preview_handoff_policy absent={0};assert(qq_preview_handoff_check(&absent,0,&receipt)<0&&reads==before);}
 for(i=0;i<2;i++){role=i;processes();assert(!qq_preview_handoff_check(&policy,role,&receipt));assert(receipt.self==100&&receipt.launcher==101+role&&receipt.manager==105+role);assert(!qq_preview_handoff_recheck(&receipt));}
 role=0;processes();assert(!qq_preview_handoff_check(&policy,role,&receipt));reused=1;statfile(101,102);assert(qq_preview_handoff_recheck(&receipt)<0);reused=0;processes();
 bad_parent=1;assert(qq_preview_handoff_check(&policy,0,&receipt)<0);bad_parent=0;
 spider_live=1;assert(qq_preview_handoff_check(&policy,0,&receipt)<0);spider_live=0;
 sound_live=1;assert(qq_preview_handoff_check(&policy,0,&receipt)<0);sound_live=0;
 registration(1);assert(qq_preview_handoff_check(&policy,0,&receipt)<0);registration(0);
 policy.launcher.sha256[0]^=1;assert(qq_preview_handoff_check(&policy,0,&receipt)<0);policy.launcher.sha256[0]^=1;
 spider[0x4ce1c0]=0;identity(&policy.spider,spider,0x4ce1c4);file("/usr/local/bin/SpiderApp",spider,0x4ce1c4);assert(qq_preview_handoff_check(&policy,0,&receipt)<0);
 assert(qq_preview_process_stat("bad",100,&parent,&birth)<0);assert(qq_preview_process_stat("100 (bad) S 1",100,&parent,&birth)<0);
 free(spider);return 0;
}
