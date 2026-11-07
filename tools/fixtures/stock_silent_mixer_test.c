/* PC-only device-model contract; no sound or player device is opened. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "stock_silent_mixer_model.h"
#ifdef TEST_GPL_AUDIO_ABI
#include "icx1087_audio.h"
typedef char play_abi[(AUDIO_SE_PLAY==0x40046115)?1:-1];
typedef char stop_abi[(AUDIO_SE_STOP==0x6116)?1:-1];
typedef char sync_abi[(AUDIO_SE_SYNC==0x6117)?1:-1];
typedef char status_abi[(AUDIO_SE_GET_STATUS==0x80046118)?1:-1];
#endif
int main(void){
 unsigned requests[]={0x40046115,0x6116,0x6117};
 assert(silent_mixer==-1&&silent_beep==-1);
 for(unsigned i=0;i<sizeof requests/sizeof requests[0];i++){
  errno=77;assert(silent_mixer_ioctl(requests[i],0)==0&&errno==77);
  assert(silent_mixer_ioctl(requests[i],(void *)1)==0); /* No payload access. */
 }
 unsigned value=99;assert(!silent_mixer_ioctl(0x80046118,&value)&&value==2);
 errno=0;assert(silent_mixer_ioctl(0x80046118,0)==-1&&errno==EFAULT);
 value=0x2020;assert(!silent_mixer_ioctl(0xc0044d00,&value));
 value=0;assert(!silent_mixer_ioctl(0x80044d00,&value)&&value==0x2020);
 value=0x00001f1f;assert(!silent_mixer_ioctl(0x40046101,&value));
 value=0;assert(!silent_mixer_ioctl(0x80046102,&value)&&value==0x1f1f);
 value=4;assert(silent_mixer_ioctl(0x40046105,&value)==-1&&errno==EINVAL);
 assert(silent_mixer_ioctl(0x6119,(void *)1)==-1&&errno==EOPNOTSUPP);
 assert(!silent_beep_ioctl(0x6208,0));
 value=0;assert(!silent_beep_ioctl(0x80046202,&value)&&value==6);
 puts("STOCK_SILENT_MIXER_MODEL_PASS");return 0;
}
