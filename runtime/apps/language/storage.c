#include "storage.h"
#include "preference.h"
#include "package.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
#include "../../store/target_abi.h"
extern int hb_language_sscanf(const char*,const char*,...) __asm__("sscanf");
extern int hb_language_statfs(const char*,void*) __asm__("statfs");
static unsigned value32(const unsigned char*p){return (unsigned)p[0]|(unsigned)p[1]<<8|(unsigned)p[2]<<16|(unsigned)p[3]<<24;}
static int stats(const char*path,int writing){unsigned char b[128]={0};if(hb_language_statfs(path,b)||value32(b)!=0x4d44)return 0;return !writing||value32(b+16)>=8;}
static int mounts_ok(void){FILE*f=fopen("/proc/mounts","rb");if(!f)return 0;char line[1024],dev[128],mount[256],type[64],options[256];int found=0,bad=0;while(fgets(line,sizeof line,f)){if(hb_language_sscanf(line,"%127s %255s %63s %255s",dev,mount,type,options)!=4)continue;if(strcmp(mount,"/contents"))continue;if(found++||strcmp(type,"vfat")||(strcmp(dev,"/dev/mtdblock/2")&&strcmp(dev,"/dev/mtdblock2")))bad=1;if(!strncmp(options,"ro,",3)||!strcmp(options,"ro"))bad=1;}if(ferror(f))bad=1;if(fclose(f))bad=1;return found==1&&!bad;}
static int same_directory(int fd,unsigned long long device){struct stat s;return !fstat(fd,&s)&&S_ISDIR(s.st_mode)&&s.st_dev==device;}
static int fd_path(char*p,int fd,const char*name){return snprintf(p,128,"/proc/self/fd/%d/%s",fd,name)>0;}
static int child_directory(int parent,const char*name,unsigned long long device,int create){char p[128];fd_path(p,parent,name);int fd=open(p,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0&&errno==ENOENT&&create){if(mkdir(p,0700))return -1;fd=open(p,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);}if(fd>=0&&!same_directory(fd,device)){close(fd);fd=-1;}return fd;}
static int user_root(int create,unsigned long long*device){struct stat root,contents;if(!mounts_ok()||lstat("/",&root)||lstat("/contents",&contents)||!S_ISDIR(contents.st_mode)||root.st_dev==contents.st_dev||!stats("/contents",create))return -1;*device=contents.st_dev;int fd=open("/contents",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd>=0&&!same_directory(fd,*device)){close(fd);fd=-1;}return fd;}
static int storage(int create,unsigned long long*device){int fd=user_root(create,device);if(fd<0)return -1;const char*parts[]={"HOMEBREW","data","language"};for(unsigned i=0;i<3;i++){int next=child_directory(fd,parts[i],*device,create&&i>0);close(fd);fd=next;if(fd<0)return -1;}return fd;}
int hb_language_packages_fd(unsigned long long*device){if(!device)return -1;int fd=user_root(0,device);if(fd<0)return -1;const char*parts[]={"HOMEBREW","languages"};for(unsigned i=0;i<2;i++){int next=child_directory(fd,parts[i],*device,0);close(fd);fd=next;if(fd<0)return -1;}return fd;}

static int file_ok(const char*p,unsigned long long device,int absent){struct stat s;if(lstat(p,&s))return absent&&errno==ENOENT;return S_ISREG(s.st_mode)&&s.st_nlink==1&&s.st_dev==device;}
int hb_language_saved_choice(void){unsigned long long dev;int dir=storage(0,&dev);if(dir<0)return -2;char path[128];fd_path(path,dir,"ui-language");if(!file_ok(path,dev,1)){close(dir);return -2;}int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);close(dir);if(fd<0)return errno==ENOENT?-1:-2;struct stat s;char b[8];int n=-1;if(!fstat(fd,&s)&&S_ISREG(s.st_mode)&&s.st_dev==dev&&s.st_nlink==1)n=(int)read(fd,b,sizeof b);close(fd);return n<0?-2:hb_language_parse(b,(unsigned)n,-1);}
static int save_text(const char*data,unsigned bytes){unsigned long long dev;int dir=storage(1,&dev);if(dir<0)return -2;char target[128],temp[128],parent[128];fd_path(target,dir,"ui-language");fd_path(temp,dir,".ui-language.tmp");snprintf(parent,sizeof parent,"/proc/self/fd/%d",dir);if(!file_ok(target,dev,1)||!file_ok(temp,dev,1)||!stats(parent,1)){close(dir);return -2;}if(unlink(temp)&&errno!=ENOENT){close(dir);return -1;}int fd=open(temp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0){close(dir);return -1;}struct stat s;int bad=fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_dev!=dev||s.st_nlink!=1;unsigned done=0;while(!bad&&done<bytes){ssize_t n=write(fd,data+done,bytes-done);if(n<0&&errno==EINTR)continue;if(n<=0){bad=1;break;}done+=(unsigned)n;}if(!bad&&fsync(fd))bad=1;if(close(fd))bad=1;if(!bad&&(!file_ok(target,dev,1)||rename(temp,target)))bad=1;if(bad){unlink(temp);close(dir);return -1;}int sync_error=fsync(dir);close(dir);return sync_error?1:0;}

int hb_language_save(int choice){return choice==1?save_text("en\n",3):choice==7?save_text("jp\n",3):choice==-1?save_text("stock\n",6):-1;}
int hb_language_save_id(const char*id){if(!id||(!hb_lp_id(id)&&strcmp(id,"stock")))return -1;char data[34];unsigned n=(unsigned)strlen(id);if(!n||n>32)return -1;memcpy(data,id,n);data[n++]='\n';return save_text(data,n);}
int hb_language_saved_id(char out[33]){if(!out)return -2;out[0]=0;unsigned long long dev;int dir=storage(0,&dev);if(dir<0)return -2;char path[128];fd_path(path,dir,"ui-language");if(!file_ok(path,dev,1)){close(dir);return -2;}int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);int open_error=errno;close(dir);if(fd<0)return open_error==ENOENT?-1:-2;struct stat st;char data[34];int n=-1;if(!fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_dev==dev&&st.st_nlink==1&&st.st_size>0&&st.st_size<=33)n=(int)read(fd,data,sizeof data);close(fd);return n>0&&hb_lp_choice(data,(unsigned)n,out)?0:-2;}
