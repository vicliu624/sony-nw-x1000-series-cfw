#include "fm_posix.h"
static int cancelled(void *p){struct fm_posix *s=p;return !s->stop||*s->stop;}
static int audio_control(void *p,uint32_t command,int32_t *value){struct fm_posix *s=p;return s->mixer<0?-1:fm_os_ioctl(s->mixer,command,value);}
static int tuner_control(void *p,uint32_t command,void *value){
 struct fm_posix *s=p;
 if(s->tuner<0||(command==FM_VIDIOCSFREQ&&cancelled(s)))return -1;
 return fm_os_ioctl(s->tuner,command,value);
}
static int wait_ms(void *p,unsigned ms){
 if(ms>1000||cancelled(p))return -1;
 if(fm_os_usleep(ms*1000)<0||cancelled(p))return -1;
 return 0;
}
static int open_audio(void *p,struct fm_audio_transport *out){
 struct fm_posix *s=p;if(cancelled(s)||s->mixer>=0||s->tuner>=0)return -1;
 s->mixer=fm_os_open("/dev/sound/mixer",2);
 if(s->mixer<0)return -1;
 *out=(struct fm_audio_transport){s,audio_control};return 0;
}
static int close_audio(void *p){struct fm_posix *s=p;int fd=s->mixer;s->mixer=-1;return fd<0?0:fm_os_close(fd);}
static int open_tuner(void *p,struct fm_tuner_transport *out){
 struct fm_posix *s=p;if(cancelled(s)||s->mixer<0||s->tuner>=0)return -1;
 /* Read-only open matches stock APCFmDevice; its driver still performs writes. */
 s->tuner=fm_os_open("/dev/v4l/radio0",0);
 if(s->tuner<0)return -1;
 *out=(struct fm_tuner_transport){s,tuner_control,wait_ms};return 0;
}
static int close_tuner(void *p){struct fm_posix *s=p;int fd=s->tuner;s->tuner=-1;return fd<0?0:fm_os_close(fd);}
struct fm_session_ops fm_posix_ops(struct fm_posix *s,volatile int *stop){
 s->mixer=s->tuner=-1;s->stop=stop;
 return (struct fm_session_ops){s,open_audio,close_audio,open_tuner,close_tuner,cancelled};
}
