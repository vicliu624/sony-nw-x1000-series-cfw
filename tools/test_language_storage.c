#define _GNU_SOURCE
#include "../runtime/apps/language/storage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include <assert.h>
static char root[1024];static int bad_fs,no_space,fail_sync,fail_rename,short_write,interrupted;static unsigned writes;
extern FILE*__real_fopen(const char*,const char*);extern int __real_open(const char*,int,...);extern int __real_lstat(const char*,struct stat*);extern int __real_fstat(int,struct stat*);extern int __real_fsync(int);extern int __real_rename(const char*,const char*);extern ssize_t __real_write(int,const void*,size_t);
static const char*translate(const char*p,char*b){if(!strncmp(p,"/contents",9)&&(p[9]==0||p[9]=='/')){snprintf(b,2048,"%s%s",root,p);return b;}return p;}
FILE*__wrap_fopen(const char*p,const char*m){char b[2048];if(!strcmp(p,"/proc/mounts")){snprintf(b,sizeof b,"%s/mounts",root);return __real_fopen(b,m);}return __real_fopen(translate(p,b),m);}
int __wrap_lstat(const char*p,struct stat*s){char b[2048];int n=__real_lstat(translate(p,b),s);if(!n)s->st_dev=!strcmp(p,"/")?1:42;return n;}
int __wrap_fstat(int fd,struct stat*s){int n=__real_fstat(fd,s);if(!n)s->st_dev=42;return n;}
static void put(unsigned char*p,unsigned n){p[0]=n;p[1]=n>>8;p[2]=n>>16;p[3]=n>>24;}
int test_statfs(const char*,void*) __asm__("statfs");
int test_statfs(const char*p,void*out){assert(!strcmp(p,"/contents")||!strncmp(p,"/proc/self/fd/",14));memset(out,0,64);put(out,bad_fs?0xef53:0x4d44);put((unsigned char*)out+16,no_space?0:1000);return 0;}
static void pinned(const char*p){assert(!strncmp(p,"/proc/self/fd/",14));int fd=atoi(p+14);char path[128],resolved[2048];snprintf(path,sizeof path,"/proc/self/fd/%d",fd);ssize_t n=readlink(path,resolved,sizeof resolved-1);assert(n>0);resolved[n]=0;assert(!strncmp(resolved,root,strlen(root)));}
int __wrap_open(const char*p,int flags,...){char b[2048];if(flags&(O_WRONLY|O_RDWR)){pinned(p);assert(flags&O_EXCL);}return __real_open(translate(p,b),flags,0600);}
ssize_t __wrap_write(int fd,const void*p,size_t n){writes++;if(interrupted){interrupted=0;errno=EINTR;return -1;}return __real_write(fd,p,short_write&&n>1?1:n);}
int __wrap_fsync(int fd){struct stat s;assert(!__real_fstat(fd,&s));if(fail_sync==1&&S_ISREG(s.st_mode)){errno=EIO;return -1;}if(fail_sync==2&&S_ISDIR(s.st_mode)){errno=EINVAL;return -1;}return __real_fsync(fd);}
int __wrap_rename(const char*a,const char*b){pinned(a);pinned(b);if(fail_rename){errno=EIO;return -1;}return __real_rename(a,b);}
static void mount_data(int wrong){char p[2048];snprintf(p,sizeof p,"%s/mounts",root);FILE*f=__real_fopen(p,"wb");assert(f);fputs(wrong?"/dev/root /contents ext2 rw 0 0\n":"/dev/mtdblock/2 /contents vfat rw 0 0\n",f);assert(!fclose(f));}
int main(int argc,char**argv){assert(argc==2);assert(strlen(argv[1])<sizeof root);strcpy(root,argv[1]);char p[2048];snprintf(p,sizeof p,"%s/contents",root);assert(!mkdir(p,0700)||errno==EEXIST);snprintf(p,sizeof p,"%s/contents/HOMEBREW",root);assert(!mkdir(p,0700)||errno==EEXIST);mount_data(0);assert(hb_language_save(44)==-1&&writes==0);assert(hb_language_save(1)==0&&hb_language_saved_choice()==1);assert(hb_language_save(7)==0&&hb_language_saved_choice()==7);assert(hb_language_save(-1)==0&&hb_language_saved_choice()==-1);char selected[33];assert(hb_language_save_id("zh-CN")==0&&hb_language_saved_id(selected)==0&&!strcmp(selected,"zh-CN"));unsigned old_writes=writes;assert(hb_language_save_id("../jp")==-1&&writes==old_writes);short_write=1;interrupted=1;assert(hb_language_save(1)==0&&hb_language_saved_choice()==1);short_write=0;fail_sync=1;assert(hb_language_save(7)==-1&&hb_language_saved_choice()==1);fail_sync=0;fail_rename=1;assert(hb_language_save(7)==-1&&hb_language_saved_choice()==1);fail_rename=0;unsigned old=writes;no_space=1;assert(hb_language_save(7)==-2&&writes==old);no_space=0;bad_fs=1;assert(hb_language_save(7)==-2&&writes==old);bad_fs=0;mount_data(1);assert(hb_language_save(7)==-2&&writes==old);mount_data(0);fail_sync=2;assert(hb_language_save(7)==1&&hb_language_saved_choice()==7);fail_sync=0;snprintf(p,sizeof p,"%s/contents/HOMEBREW/data/language/ui-language",root);assert(!unlink(p));assert(!symlink("/not-a-language-preference",p));old=writes;assert(hb_language_save(1)==-2&&writes==old);assert(!unlink(p));puts("Language save: en/jp/original, pinned external directories, short/EINTR writes, fsync/rename errors, full/wrong storage and symlink rejection passed");return 0;}
