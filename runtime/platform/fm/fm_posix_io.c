/* Only this translation unit calls libc device operations. Tests replace it. */
#include "fm_posix.h"
#include <fcntl.h>
#include <unistd.h>
/* Only fixed non-time ARM32 requests below are allowed. Match the stock
 * libc ioctl symbol rather than modern headers redirecting to time64. */
extern int fm_stock_ioctl(int,unsigned long,void *) __asm__("ioctl");
int fm_os_open(const char *path,int flags){return open(path,flags);}
int fm_os_close(int fd){return close(fd);}
int fm_os_ioctl(int fd,unsigned long request,void *data){
 switch(request){
 case FM_VIDIOC_PUTREG:
 case FM_VIDIOCGAUDIO:case FM_VIDIOCSAUDIO:
 case FM_VIDIOCGCAP:case FM_VIDIOCGTUNER:case FM_VIDIOCGFREQ:case FM_VIDIOCSFREQ:case FM_VIDIOC_GETREG:
 case FM_AUDIO_GET_CODEC_POWERDOWN:case FM_AUDIO_SET_MUTE:case FM_AUDIO_GET_MUTE:
 case FM_AUDIO_SET_SOURCE:case FM_AUDIO_GET_SOURCE:case FM_AUDIO_SET_OUTPUT:case FM_AUDIO_GET_OUTPUT:
 case FM_AUDIO_SET_PCM:case FM_AUDIO_GET_PCM:case FM_AUDIO_SET_ADC:case FM_AUDIO_GET_ADC:
  return fm_stock_ioctl(fd,request,data);
 default:return -1;
 }
}
int fm_os_usleep(unsigned duration){return usleep(duration);}
