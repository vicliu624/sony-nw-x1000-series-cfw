#define _XOPEN_SOURCE 700
#include "qqmusic_preview_device_posix.h"
#include "../fm-radio/fm_audio.h"
#include "../../store/stock_stat64.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int preview_open(const char *,int,...) __asm__("open");
extern int preview_ioctl(int,unsigned long,void *) __asm__("ioctl");
extern int preview_fcntl(int,int,...) __asm__("fcntl");
#ifdef HB_STORE_SONY_LIBC
extern int preview_fxstat64(int,int,void *) __asm__("__fxstat64");
extern int preview_lxstat64(int,const char *,void *) __asm__("__lxstat64");
static int node_raw(const unsigned char raw[96],unsigned major,unsigned minor){
 struct hb_stock_stat s;uint64_t rdev=0;unsigned i;
 if(hb_stock_stat64_decode(raw,96,3,&s)||!S_ISCHR(s.mode))return -1;
 for(i=0;i<8;i++)rdev|=(uint64_t)raw[32+i]<<(i*8);
 /* Exact small dev_t values for the pinned devfs nodes, no host macro ABI. */
 return rdev==((uint64_t)major<<8|minor)?0:-1;
}
static int fd_identity(int fd,unsigned major,unsigned minor){unsigned char raw[96] __attribute__((aligned(8)));return preview_fxstat64(3,fd,raw)||node_raw(raw,major,minor)?-1:0;}
static int path_identity(const char *path,unsigned major,unsigned minor){unsigned char raw[96] __attribute__((aligned(8)));return preview_lxstat64(3,path,raw)||node_raw(raw,major,minor)?-1:0;}
#else
static int fd_identity(int fd,unsigned major,unsigned minor){struct stat s;return fstat(fd,&s)||!S_ISCHR(s.st_mode)||(uint64_t)s.st_rdev!=((uint64_t)major<<8|minor)?-1:0;}
static int path_identity(const char *path,unsigned major,unsigned minor){struct stat s;return lstat(path,&s)||!S_ISCHR(s.st_mode)||(uint64_t)s.st_rdev!=((uint64_t)major<<8|minor)?-1:0;}
#endif
static int confirmed_close(int fd){
 int rc=close(fd),error;if(!rc)return 0;error=errno;
 /* A negative close result is not automatically retried or accepted. Only
  * an explicit EBADF readback confirms that this process no longer owns fd. */
 if(preview_fcntl(fd,F_GETFD)<0&&errno==EBADF)return 0;
 return -error;
}
static int preflight(void *context,uint64_t generation){
 struct qq_preview_device_posix *p=context;
 if(!generation||p->uncertain||*p->stop||qq_workspace_check(p->workspace)||qq_preview_handoff_check(p->policy,p->role,&p->handoff))return -1;
 p->generation=generation;p->parent=(unsigned)getppid();return 0;
}
static int retain_guard(void *context){
 struct qq_preview_device_posix *p=context;struct stat s;int fd;
 if(!p->generation||p->retained_guard>=0||*p->stop||qq_workspace_check(p->workspace))return -1;
 fd=dup(p->workspace->lock);if(fd<0)return -1;
 if(preview_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||(uint64_t)s.st_dev!=p->workspace->volume.device||(uint64_t)s.st_ino!=p->workspace->inode){if(confirmed_close(fd))p->uncertain=1;return -1;}
 p->retained_guard=fd;return fd;
}
static int drop_guard(void *context,int fd){struct qq_preview_device_posix *p=context;int rc;if(fd<0||fd!=p->retained_guard)return -1;p->retained_guard=-1;rc=confirmed_close(fd);return rc;}
static int open_device(void *context,const char *path,int flags){
 struct qq_preview_device_posix *p=context;unsigned minor;int fd;
 if(!p->generation||p->retained_guard<0||*p->stop||qq_workspace_check(p->workspace)||qq_preview_handoff_recheck(&p->handoff))return -EACCES;
 if(!strcmp(path,"/dev/sound/mixer")&&flags==2)minor=0;
 else if(!strcmp(path,"/dev/sound/dsp")&&flags==0x801)minor=3;
 else return -EACCES;
 if(path_identity(path,14,minor))return -ENODEV;
 fd=preview_open(path,flags|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return -errno;
 if(preview_fcntl(fd,F_SETFD,FD_CLOEXEC)<0){int error=errno;if(confirmed_close(fd))p->uncertain=1;return -error;}
 return fd;
}
static int identity(void *context,int fd,unsigned major,unsigned minor){(void)context;return major!=14||(minor!=0&&minor!=3)?-1:fd_identity(fd,major,minor);}
static int close_fd(void *context,int fd){int rc;(void)context;rc=confirmed_close(fd);return rc;}
static int control(void *context,int fd,uint32_t request,int32_t *value){
 struct qq_preview_device_posix *p=context;unsigned minor;int rc;
 if(!p->generation||p->retained_guard<0)return -EACCES;
 switch(request){
 case 0x5000u:case 0xc0045005u:case 0xc0045006u:case 0xc0045002u:
 case 0xc0045004u:case 0x80045017u:minor=3;break;
 case FM_AUDIO_GET_MUTE:case FM_AUDIO_SET_MUTE:case FM_AUDIO_GET_SOURCE:case FM_AUDIO_SET_SOURCE:
 case FM_AUDIO_GET_OUTPUT:case FM_AUDIO_SET_OUTPUT:case FM_AUDIO_GET_PCM:case FM_AUDIO_SET_PCM:
 case FM_AUDIO_GET_ADC:case FM_AUDIO_SET_ADC:case FM_AUDIO_GET_CODEC_POWERDOWN:case 0x4004610du:minor=0;break;
 default:return -EACCES;
 }
 if(fd_identity(fd,14,minor))return -ENODEV;
 if(request!=0x5000u&&!value)return -EINVAL;
 if((request==0xc0045002u&&*value!=44100)||(request==0xc0045005u&&*value!=16)||(request==0xc0045006u&&*value!=2))return -EINVAL;
 rc=preview_ioctl(fd,request,value);return rc<0?-errno:0;
}
static int write_pcm(void *context,int fd,const unsigned char *data,unsigned n){
 struct qq_preview_device_posix *p=context;ssize_t rc;
 if(!p->generation||p->retained_guard<0||*p->stop||(unsigned)getppid()!=p->parent)return -ECANCELED;
 if(!data||!n||n>4096||fd_identity(fd,14,3))return -EINVAL;
 rc=write(fd,data,n);return rc<0?-errno:(int)rc;
}
static int producer_exited(void *context,uint64_t generation){struct qq_preview_device_posix *p=context;return !p->uncertain&&generation==p->generation?p->producer_exited(p->producer_context,generation):-1;}
int qq_preview_device_posix_io(struct qq_preview_device_posix *p,struct qq_preview_device_io *out){
 if(out)memset(out,0,sizeof(*out));
 if(!p||!out||p->generation||!p->policy||!p->workspace||p->workspace->lock<0||!p->stop||*p->stop||p->role>1||!p->producer_exited)return -1;
 p->generation=0;p->retained_guard=-1;p->parent=0;memset(&p->handoff,0,sizeof(p->handoff));memset(out,0,sizeof(*out));
 out->context=p;out->preflight=preflight;out->retain_guard=retain_guard;out->drop_guard=drop_guard;out->open=open_device;out->identity=identity;out->close=close_fd;out->control=control;out->write=write_pcm;out->producer_exited=producer_exited;return 0;
}
