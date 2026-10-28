#define _XOPEN_SOURCE 700
#include "../../runtime/apps/qqmusic/qqmusic_preview_device_posix.h"
#include "../../runtime/apps/fm-radio/fm_audio.h"
#include <assert.h>
#include <string.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
static unsigned denied,node_bad,fd_bad,parent_dead,opens,controls,writes,guard_closed,close_bad,close_consumed,fcntl_bad;
static volatile int stop_flag;
static void put32(unsigned char *p,unsigned n){unsigned i;for(i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i));}
static int raw_stat(void *out,int fd){
 unsigned char *p=out;unsigned mode=fd==50||fd==60?S_IFREG:S_IFCHR;unsigned device=fd==10?0xe00:0xe03;
 memset(p,0,96);put32(p,7);put32(p+16,mode|0600);put32(p+20,1);put32(p+44,4096);put32(p+88,42);
 if(fd_bad)device=0x103;
 put32(p+32,device);return 0;
}
int __wrap___fxstat64(int version,int fd,void *out){assert(version==3);return raw_stat(out,fd);}
int __wrap___lxstat64(int version,const char *path,void *out){int result;assert(version==3);result=raw_stat(out,strstr(path,"mixer")?10:11);if(node_bad)put32((unsigned char *)out+32,0x103);return result;}
#ifndef HB_STORE_SONY_LIBC
int __wrap_fstat(int fd,struct stat *out){memset(out,0,sizeof(*out));out->st_mode=(fd==50||fd==60?S_IFREG:S_IFCHR)|0600;out->st_dev=7;out->st_ino=42;out->st_nlink=1;out->st_rdev=fd_bad?0x103:fd==10?0xe00:0xe03;return 0;}
int __wrap_lstat(const char *path,struct stat *out){int rc=__wrap_fstat(strstr(path,"mixer")?10:11,out);if(node_bad)out->st_rdev=0x103;return rc;}
#endif
pid_t __wrap_getppid(void){return parent_dead?1:123;}
int __wrap_dup(int fd){assert(fd==50);return 60;}
int __wrap_close(int fd){assert(fd==10||fd==11||fd==60);if(fd==60)guard_closed++;if(close_bad){errno=EINTR;return -1;}return 0;}
int __wrap_fcntl(int fd,int cmd,...){va_list ap;int value;assert(fd==10||fd==11||fd==60);if(cmd==F_GETFD){if(close_consumed){errno=EBADF;return -1;}return FD_CLOEXEC;}assert(cmd==F_SETFD);va_start(ap,cmd);value=va_arg(ap,int);va_end(ap);assert(value==FD_CLOEXEC);if(fcntl_bad){errno=EIO;return -1;}return 0;}
int __wrap_open(const char *path,int flags,...){assert(flags&O_NOFOLLOW);opens++;if(!strcmp(path,"/dev/sound/mixer"))return 10;assert(!strcmp(path,"/dev/sound/dsp")&&(flags&O_NONBLOCK));return 11;}
int __wrap_open64(const char *path,int flags,...){return __wrap_open(path,flags);}
ssize_t __wrap_write(int fd,const void *p,size_t n){assert(fd==11&&p&&n&&n<=4096);writes++;return n>3?3:(ssize_t)n;}
int __wrap_ioctl(int fd,unsigned long request,...){void *p;va_list ap;assert(fd==10||fd==11);controls++;va_start(ap,request);p=va_arg(ap,void *);va_end(ap);if(request==FM_AUDIO_GET_MUTE)*(int32_t *)p=31;return 0;}
int qq_workspace_check(void *workspace){assert(workspace);return denied?-1:0;}
int qq_preview_handoff_check(const struct qq_preview_handoff_policy *p,unsigned role,struct qq_preview_handoff_receipt *r){assert(p&&role==1);memset(r,0,sizeof(*r));r->self=42;return denied?-1:0;}
int qq_preview_handoff_recheck(const struct qq_preview_handoff_receipt *r){assert(r->self==42);return denied?-1:0;}
static int producer(void *context,uint64_t generation){assert(context==(void *)1&&generation==7);return 1;}
int main(void){
 struct qq_preview_handoff_policy policy={0};struct qq_workspace workspace={0};struct qq_preview_device_posix p={0};struct qq_preview_device_io io={0};int32_t value;unsigned before;unsigned char pcm[8]={0};
 workspace.lock=50;workspace.volume.device=7;workspace.inode=42;p.policy=&policy;p.workspace=&workspace;p.stop=&stop_flag;p.role=1;p.producer_context=(void *)1;p.producer_exited=producer;
 assert(!qq_preview_device_posix_io(&p,&io));assert(io.open(io.context,"/dev/sound/mixer",2)==-EACCES&&!opens);
 denied=1;assert(io.preflight(io.context,7)<0&&!p.generation);denied=0;assert(!io.preflight(io.context,7));
 assert(io.retain_guard(io.context)==60);node_bad=1;assert(io.open(io.context,"/dev/sound/mixer",2)==-ENODEV&&!opens);node_bad=0;
 assert(io.open(io.context,"/dev/sound/mixer",2)==10);assert(!io.identity(io.context,10,14,0));assert(io.identity(io.context,10,14,3)<0);
 assert(io.open(io.context,"/dev/sound/dsp",0x801)==11);assert(!io.identity(io.context,11,14,3));assert(io.open(io.context,"/dev/null",2)==-EACCES);
 before=controls;value=0;assert(io.control(io.context,11,0xc0045002u,&value)==-EINVAL&&controls==before);value=48000;assert(io.control(io.context,11,0xc0045002u,&value)==-EINVAL&&controls==before);
 value=44100;assert(!io.control(io.context,11,0xc0045002u,&value));value=1;assert(io.control(io.context,11,0xc0045006u,&value)==-EINVAL);value=2;assert(!io.control(io.context,11,0xc0045006u,&value));
 assert(!io.control(io.context,11,0x5000u,0));assert(io.control(io.context,11,0x5001u,0)==-EACCES);
 value=0;assert(!io.control(io.context,11,0xc0045004u,&value));assert(!io.control(io.context,11,0x80045017u,&value));
 assert(io.control(io.context,11,0x80045017u,0)==-EINVAL);assert(io.control(io.context,11,0x5008u,0)==-EACCES);
 assert(io.control(io.context,10,0x80045017u,&value)==-ENODEV);
 value=0;assert(!io.control(io.context,10,FM_AUDIO_GET_MUTE,&value)&&value==31);assert(io.control(io.context,11,FM_AUDIO_GET_MUTE,&value)==-ENODEV);
 assert(io.write(io.context,11,pcm,sizeof(pcm))==3&&writes==1);parent_dead=1;assert(io.write(io.context,11,pcm,sizeof(pcm))==-ECANCELED&&writes==1);parent_dead=0;
 stop_flag=1;assert(io.write(io.context,11,pcm,sizeof(pcm))==-ECANCELED);assert(!io.control(io.context,11,0x5000u,0));stop_flag=0;
 assert(io.producer_exited(io.context,6)<0&&io.producer_exited(io.context,7)==1);
 close_bad=close_consumed=1;assert(!io.close(io.context,11));close_bad=close_consumed=0;
 assert(!io.close(io.context,10)&&!io.drop_guard(io.context,60)&&guard_closed==1);
 assert(qq_preview_device_posix_io(&p,&io)<0&&!io.open); /* live/used context cannot be rebound */
 memset(&p,0,sizeof(p));p.policy=&policy;p.workspace=&workspace;p.stop=&stop_flag;p.role=1;p.producer_context=(void *)1;p.producer_exited=producer;
 assert(!qq_preview_device_posix_io(&p,&io)&&!io.preflight(io.context,7));fcntl_bad=close_bad=1;
 assert(io.retain_guard(io.context)<0&&p.uncertain&&io.producer_exited(io.context,7)<0);
 return 0;
}
