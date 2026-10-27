#include "fm_audio.h"
#include <string.h>
static int set(struct fm_audio *a,uint32_t command,int32_t value){
 uint32_t get;
 switch(command){
 case FM_AUDIO_SET_MUTE:get=FM_AUDIO_GET_MUTE;break;
 case FM_AUDIO_SET_SOURCE:get=FM_AUDIO_GET_SOURCE;break;
 case FM_AUDIO_SET_OUTPUT:get=FM_AUDIO_GET_OUTPUT;break;
 case FM_AUDIO_SET_PCM:get=FM_AUDIO_GET_PCM;break;
 case FM_AUDIO_SET_ADC:get=FM_AUDIO_GET_ADC;break;
 default:return -1;
 }
 int32_t expected=value,actual=0;
 if(a->io.control(a->io.context,command,&value)<0||a->io.control(a->io.context,get,&actual)<0)return -1;
 if(command==FM_AUDIO_SET_MUTE){expected&=31;actual&=31;}
 return actual==expected?0:-1;
}
int fm_audio_restore(struct fm_audio *a){
 if(!a||!a->dirty)return 0;
 int failed=set(a,FM_AUDIO_SET_MUTE,31)<0;
 /* Try every restoration even after an individual failure. Only unmute after
  * all routing and mix state has been restored successfully. */
 if(set(a,FM_AUDIO_SET_OUTPUT,a->saved[2])<0)failed=1;
 if(set(a,FM_AUDIO_SET_SOURCE,a->saved[1])<0)failed=1;
 if(set(a,FM_AUDIO_SET_PCM,a->saved[3])<0)failed=1;
 if(set(a,FM_AUDIO_SET_ADC,a->saved[4])<0)failed=1;
 int32_t current=-1;
 if(a->io.control(a->io.context,FM_AUDIO_GET_MUTE,&current)<0||((current^a->saved[0])&0x100))failed=1;
 if(!failed&&set(a,FM_AUDIO_SET_MUTE,a->saved[0]&31)<0)failed=1;
 if(failed)set(a,FM_AUDIO_SET_MUTE,31);
 a->playing=0;a->restore_failed=failed;
 if(!failed)a->dirty=0;
 return failed?-1:0;
}
int fm_audio_prepare(struct fm_audio *a,struct fm_audio_transport io){
 if(!a||!io.control)return -1;
 /* Caller must finish restoration before preparing this object again. */
 if(a->dirty)return -1;
 memset(a,0,sizeof(*a));a->io=io;
 int32_t powerdown=-1;
 /* Require existing codec power. Do not reset/restart the codec or write a
  * power proc node inferred only from a string in the stock program. */
 if(io.control(io.context,FM_AUDIO_GET_CODEC_POWERDOWN,&powerdown)<0||powerdown!=0)return -1;
 const uint32_t commands[]={FM_AUDIO_GET_MUTE,FM_AUDIO_GET_SOURCE,FM_AUDIO_GET_OUTPUT,FM_AUDIO_GET_PCM,FM_AUDIO_GET_ADC};
 for(unsigned i=0;i<5;i++)if(io.control(io.context,commands[i],&a->saved[i])<0)return -1;
 /* This public ioctl cannot restore driver-internal mute bit0x100.
  * A pre-existing internal mute requires a different, proven handoff state. */
 if(a->saved[0]&0x100)return -1;
 if(a->saved[1]<0||a->saved[1]>6||a->saved[2]<0||a->saved[2]>3)return -1;
 a->dirty=1;
 /* Leave user analog headphone volume untouched; silence the PCM mix and
  * use unity ADC mix for tuner audio. Do not unmute before successful tuning. */
 if(set(a,FM_AUDIO_SET_MUTE,31)<0||set(a,FM_AUDIO_SET_PCM,0)<0||
    set(a,FM_AUDIO_SET_ADC,0x6464)<0||set(a,FM_AUDIO_SET_SOURCE,2)<0||
    set(a,FM_AUDIO_SET_OUTPUT,0)<0){fm_audio_restore(a);return -1;}
 return 0;
}
int fm_audio_play(struct fm_audio *a){
 if(!a||!a->dirty||a->restore_failed)return -1;
 /* PCM mixing remains muted; only tuner/ADC output is enabled. */
 if(set(a,FM_AUDIO_SET_MUTE,2)<0){set(a,FM_AUDIO_SET_MUTE,31);return -1;}
 a->playing=1;return 0;
}

int fm_audio_silence(struct fm_audio *a){
 if(!a||!a->dirty)return 0;
 int result=set(a,FM_AUDIO_SET_MUTE,31);a->playing=0;return result;
}
