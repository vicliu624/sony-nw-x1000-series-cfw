#define _XOPEN_SOURCE 700
#include "qqmusic_preview_handoff.h"
#include "../../native/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern ssize_t handoff_read(int,void *,size_t) __asm__("read");
extern ssize_t handoff_readlink(const char *,char *,size_t) __asm__("readlink");
extern int handoff_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
#define QQ_APP "/contents/HOMEBREW/apps/qqmusic/app"
#define QQ_HELPER "/contents/HOMEBREW/apps/qqmusic/audio-helper"
#define LAUNCHER "/contents/HOMEBREW/launcher/app"
#define PROXY "/usr/local/bin/appproxy"
#define MANAGER "/usr/local/bin/sysmgrd"
#define SPIDER "/usr/local/bin/SpiderApp"
static int number(const char *first,const char *last,uint64_t *out){
 uint64_t n=0;if(first==last)return -1;
 while(first<last){unsigned c=(unsigned char)*first++;if(c<'0'||c>'9'||n>(UINT64_MAX-(c-'0'))/10)return -1;n=n*10+c-'0';}
 *out=n;return 0;
}
int qq_preview_process_stat(const char *text,unsigned pid,unsigned *parent,uint64_t *birth){
 const char *p,*end,*last;uint64_t n;unsigned field;
 if(!text||!parent||!birth||!pid)return -1;
 *parent=0;*birth=0;p=strchr(text,' ');if(!p||number(text,p,&n)||n!=pid||p[1]!='(')return -1;
 last=strrchr(p,')');if(!last||last[1]!=' ')return -1;p=last+2;
 for(field=3;field<=22;field++){
  if(!*p)return -1;
  end=p;while(*end&&*end!=' '&&*end!='\n')end++;
  if(field==3){if(end-p!=1)return -1;}
  if(field==4){if(number(p,end,&n)||n>2147483647u)return -1;*parent=(unsigned)n;}
  if(field==22){if(number(p,end,birth)||!*birth)return -1;return 0;}
  if(*end!=' ')return -1;
  p=end+1;
 }return -1;
}
static int path(char *out,size_t cap,unsigned pid,const char *suffix){int n=handoff_snprintf(out,cap,"/proc/%u/%s",pid,suffix);return n<0||(size_t)n>=cap?-1:0;}
static int small(const char *name,char *out,size_t cap,size_t *bytes){
 int fd,rc=-1;size_t used=0;ssize_t n;char extra;
 if(!out||cap<2)return -1;
 fd=open(name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return -1;
 while(used<cap-1){n=handoff_read(fd,out+used,cap-1-used);if(n<0&&errno==EINTR)continue;if(n<0)goto done;if(!n){out[used]=0;*bytes=used;rc=0;goto done;}used+=(size_t)n;}
 do{n=handoff_read(fd,&extra,1);}while(n<0&&errno==EINTR);
 if(!n){out[used]=0;*bytes=used;rc=0;}
done:if(close(fd))rc=-1;return rc;
}
static int process(unsigned pid,unsigned *parent,uint64_t *birth,char *exe,size_t capacity){
 char name[96],stat[2048];size_t used;ssize_t n;
 if(path(name,sizeof(name),pid,"stat")||small(name,stat,sizeof(stat),&used)||memchr(stat,0,used)||qq_preview_process_stat(stat,pid,parent,birth))return -1;
 if(path(name,sizeof(name),pid,"exe"))return -1;
 n=handoff_readlink(name,exe,capacity-1);if(n<=0||(size_t)n>=capacity-1)return -1;exe[n]=0;return 0;
}
static int image(const char *name,const struct qq_preview_image *expected,int mode1){
 struct stat before,after,named;struct hb_sha256 hash;unsigned char bytes[4096],digest[32],instruction[4]={0};uint64_t offset=0;int fd=-1,rc=-1;unsigned i;
 if(!expected||!expected->bytes||expected->bytes>32u*1024u*1024u)return -1;
 for(i=0;i<32&&expected->sha256[i]==0;i++){}
 if(i==32)return -1;
 if(lstat(name,&named)||!S_ISREG(named.st_mode)||named.st_nlink!=1)return -1;
 fd=open(name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return -1;
 if(fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_nlink!=1||(uint64_t)before.st_size!=expected->bytes||before.st_dev!=named.st_dev||before.st_ino!=named.st_ino)goto done;
 hb_sha256_init(&hash);
 while(offset<expected->bytes){
  unsigned wanted=(unsigned)(expected->bytes-offset>sizeof(bytes)?sizeof(bytes):expected->bytes-offset);ssize_t n=handoff_read(fd,bytes,wanted);
  if(n<0&&errno==EINTR)continue;
  if(n<=0||(unsigned long)n>wanted)goto done;
  if(mode1)for(i=0;i<4;i++){uint64_t at=0x4ce1c0u+i;if(at>=offset&&at<offset+(unsigned)n)instruction[i]=bytes[(size_t)(at-offset)];}
  hb_sha256_update(&hash,bytes,(unsigned)n);offset+=(unsigned)n;
 }
 {ssize_t n;do{n=handoff_read(fd,bytes,1);}while(n<0&&errno==EINTR);if(n)goto done;}
 hb_sha256_final(&hash,digest);if(memcmp(digest,expected->sha256,32)||(mode1&&memcmp(instruction,"\x01\x30\xa0\xe3",4)))goto done;
 if(fstat(fd,&after)||lstat(name,&named)||!S_ISREG(named.st_mode)||after.st_nlink!=1||named.st_nlink!=1||before.st_ino!=after.st_ino||before.st_dev!=after.st_dev||before.st_size!=after.st_size||after.st_dev!=named.st_dev||after.st_ino!=named.st_ino||after.st_size!=named.st_size)goto done;
 rc=0;
done:if(fd>=0&&close(fd))rc=-1;return rc;
}
static int registration(void){
 char data[8192],*line,*end;size_t bytes;unsigned found=0;
 if(small("/etc/AppList.conf",data,sizeof(data),&bytes)||memchr(data,0,bytes))return -1;
 line=data;
 while(*line){
  end=strchr(line,'\n');if(end)*end=0;
  while(*line==' '||*line=='\t')line++;
  if(!strncmp(line,"0x00030001",10)){
   const char *p=line+10,*tokens[]={"*",LAUNCHER,"--native"};unsigned i;
   for(i=0;i<3;i++){size_t n=strlen(tokens[i]);if(*p!=' '&&*p!='\t')return -1;while(*p==' '||*p=='\t')p++;if(strncmp(p,tokens[i],n))return -1;p+=n;}
   while(*p==' '||*p=='\t'||*p=='\r')p++;
   if(*p)return -1;
   found++;
  }
  if(!end)break;
  line=end+1;
 }
 return found==1?0:-1;
}
static int audio_target(const char *s){return !strncmp(s,"/dev/sound/",11)||!strcmp(s,"/dev/dsp")||!strcmp(s,"/dev/dsp0")||!strncmp(s,"/dev/inter_dsp",14);}
static int quiescent(unsigned self){
 DIR *all=opendir("/proc");struct dirent *entry;unsigned count=0;int rc=-1;
 if(!all)return -1;
 while((entry=readdir(all))!=0){
  uint64_t parsed;unsigned pid,parent;uint64_t birth;char exe[320],name[128],target[320];DIR *fds;struct dirent *fd;unsigned inspected=0;ssize_t n;
  if(number(entry->d_name,entry->d_name+strlen(entry->d_name),&parsed))continue;
  if(!parsed||parsed>2147483647u||++count>256)goto done;
  pid=(unsigned)parsed;
  if(pid==self)continue;
  if(!process(pid,&parent,&birth,exe,sizeof(exe))){if(!strcmp(exe,SPIDER))goto done;}
  else{
   char cmdline[2];size_t bytes;
   if(path(name,sizeof(name),pid,"cmdline")||small(name,cmdline,sizeof(cmdline),&bytes)||bytes)goto done;
  }
  if(path(name,sizeof(name),pid,"fd"))goto done;
  fds=opendir(name);if(!fds)goto done;
  while((fd=readdir(fds))!=0){
   uint64_t numeric;char file[160];int used;
   if(number(fd->d_name,fd->d_name+strlen(fd->d_name),&numeric))continue;
   if(++inspected>256){closedir(fds);goto done;}
   used=handoff_snprintf(file,sizeof(file),"%s/%s",name,fd->d_name);if(used<0||(size_t)used>=sizeof(file)){closedir(fds);goto done;}
   n=handoff_readlink(file,target,sizeof(target)-1);if(n<0){closedir(fds);goto done;}if((size_t)n>=sizeof(target)-1){closedir(fds);goto done;}target[n]=0;
   if(audio_target(target)){closedir(fds);goto done;}
  }
  if(closedir(fds))goto done;
 }
 rc=0;
done:if(closedir(all))rc=-1;return rc;
}
static int chain(unsigned role,struct qq_preview_handoff_receipt *r){
 unsigned pid=(unsigned)getpid(),parent,depth=0;uint64_t birth;char exe[320];
 memset(r,0,sizeof(*r));r->self=pid;
 if(process(pid,&parent,&birth,exe,sizeof(exe))||strcmp(exe,role?QQ_HELPER:QQ_APP)||parent!=(unsigned)getppid())return -1;
 if(role){pid=parent;if(process(pid,&parent,&r->app_birth,exe,sizeof(exe))||strcmp(exe,QQ_APP))return -1;r->app=pid;}
 else{r->app=pid;r->app_birth=birth;}
 pid=parent;if(process(pid,&parent,&r->launcher_birth,exe,sizeof(exe))||strcmp(exe,LAUNCHER))return -1;r->launcher=pid;
 do{pid=parent;if(!pid||++depth>8||process(pid,&parent,&birth,exe,sizeof(exe)))return -1;
  if(!strcmp(exe,PROXY)){r->proxy=pid;r->proxy_birth=birth;}
  else if(!strcmp(exe,MANAGER)&&r->proxy){r->manager=pid;r->manager_birth=birth;return 0;}
  else return -1;
 }while(parent!=pid);
 return -1;
}
int qq_preview_handoff_recheck(const struct qq_preview_handoff_receipt *r){
 struct qq_preview_handoff_receipt actual;unsigned role;
 if(!r||r->self!=(unsigned)getpid())return -1;
 role=r->self!=r->app;
 if(chain(role,&actual)||memcmp(&actual,r,sizeof(actual)))return -1;
 return quiescent(r->self);
}
static int complete_identity(const struct qq_preview_image *image){
 unsigned i;if(!image->bytes||image->bytes>32u*1024u*1024u)return 0;
 for(i=0;i<32;i++)if(image->sha256[i])return 1;
 return 0;
}
int qq_preview_handoff_check(const struct qq_preview_handoff_policy *p,unsigned role,struct qq_preview_handoff_receipt *out){
 struct qq_preview_handoff_receipt r;
 if(out)memset(out,0,sizeof(*out));
 if(!p||!out||role>1||!complete_identity(&p->spider)||!complete_identity(&p->launcher)||!complete_identity(&p->proxy)||!complete_identity(&p->manager)||chain(role,&r)||quiescent(r.self)||registration())return -1;
 if(image(SPIDER,&p->spider,1)||image(LAUNCHER,&p->launcher,0)||image(PROXY,&p->proxy,0)||image(MANAGER,&p->manager,0)||qq_preview_handoff_recheck(&r))return -1;
 *out=r;return 0;
}
