#include "fm_si470x.h"
#include <string.h>
#include <stddef.h>
typedef char tuner_size_check[sizeof(struct fm_v4l_tuner)==52?1:-1];
typedef char tuner_signal_check[offsetof(struct fm_v4l_tuner,signal)==50?1:-1];
typedef char capability_size_check[sizeof(struct fm_v4l_capability)==60?1:-1];
typedef char audio_size_check[sizeof(struct fm_v4l_audio)==40?1:-1];
typedef char write_register_size_check[sizeof(struct fm_v4l_write_register)==32&&offsetof(struct fm_v4l_write_register,value)==2?1:-1];
typedef char register_size_check[sizeof(struct fm_v4l_register)==32?1:-1];
/* Restrict the old private ioctl to indices whose returned halfword fits its
 * 32-byte wire buffer. Never use GETREGALL: its handler writes beyond that size. */
static int read_register(struct fm_si470x *s,unsigned index,unsigned *value){
 struct fm_v4l_register packet;
 if(index>11)return -1;
 memset(&packet,0,sizeof(packet));packet.index=index;
 if(s->io.control(s->io.context,FM_VIDIOC_GETREG,&packet)<0)return -1;
 *value=packet.values[index];return *value==65535u?-1:0;
}
/* Sony's private register-write dispatcher takes register in byte0 and the
 * little-endian halfword at byte2. Only SYSCONFIG2 (5) is writable here. */
static int write_config(struct fm_si470x *s,unsigned value){
 struct fm_v4l_write_register packet;memset(&packet,0,sizeof(packet));packet.index=5;packet.value=(uint16_t)value;
 unsigned actual;
 if(s->io.control(s->io.context,FM_VIDIOC_PUTREG,&packet)<0||read_register(s,5,&actual)||actual!=value)return -1;
 return 0;
}
int fm_si470x_restore_band(struct fm_si470x *s){
 if(!s||!s->config_dirty)return 0;
 if(write_config(s,s->original_config))return -1;
 s->config_dirty=0;return 0;
}
static int channel_for(struct fm_si470x *s,int khz,unsigned *channel){
 unsigned config;
 if(read_register(s,5,&config))return -1;
 unsigned band=(config>>6)&3,spacing=(config>>4)&3;
 if(band==3||spacing==3)return -1;
 int low=band==0?87500:76000,high=band==2?90000:108000;
 int step=spacing==0?200:spacing==1?100:50;
 if(khz<low||khz>high||(khz-low)%step)return -1;
 *channel=(unsigned)(khz-low)/step;return 0;
}
int fm_si470x_probe(struct fm_si470x *s,struct fm_tuner_transport io,struct fm_band band){
 if(!s)return -1;
 memset(s,0,sizeof(*s));
 if(!io.control||!io.wait_ms||band.low<76000||band.high>108000||band.low>band.high||
    (band.step!=50&&band.step!=100&&band.step!=200)||(band.high-band.low)%band.step)return -1;
 struct fm_v4l_capability cap;struct fm_v4l_tuner tuner;
 memset(&cap,0,sizeof(cap));memset(&tuner,0,sizeof(tuner));
 if(io.control(io.context,FM_VIDIOCGCAP,&cap)<0||
    memcmp(cap.name,"Silicon Labs. Tuner",20)||!(cap.type&2))return -1;
 if(io.control(io.context,FM_VIDIOCGTUNER,&tuner)<0||
    memcmp(tuner.name,"FM",3)||!(tuner.flags&8)||
    tuner.low>(uint32_t)band.low*16u||tuner.high<(uint32_t)band.high*16u)return -1;
 s->io=io;s->band=band;s->identity_verified=1;
 if(band.low==76000&&band.high==108000){
  unsigned original;
  if(read_register(s,5,&original)||((original>>6)&3)==3||((original>>4)&3)==3)return -1;
  /* BAND=01 is Japan-wide76-108. Keep existing50/100kHz spacing;
   * convert200kHz to100kHz when the requested100kHz grid needs it. */
  unsigned desired=(original&~0xc0u)|0x40u;
  if((original&0x30u)==0&&band.step<200)desired=(desired&~0x30u)|0x10u;
  if(desired!=original){
   s->original_config=original;s->config_dirty=1;
   /* Mark dirty before trying: failed acknowledgement can still mean a write. */
   if(write_config(s,desired)){fm_si470x_restore_band(s);return -1;}
  }
 }
 unsigned channel;if(channel_for(s,band.low,&channel)||channel_for(s,band.high,&channel)||(band.low<band.high&&channel_for(s,band.low+band.step,&channel))){return -1;}
 s->verified=1;return 0;
}
static int tune(void *context,int khz){
 struct fm_si470x *s=context;
 if(!s||!s->verified||khz<s->band.low||khz>s->band.high||(khz-s->band.low)%s->band.step)return -1;
 s->last_tuned=0;
 unsigned expected;if(channel_for(s,khz,&expected))return -1;
 uint32_t value=(uint32_t)khz*16u,actual=0;
 if(s->io.control(s->io.context,FM_VIDIOCSFREQ,&value)<0||
    s->io.control(s->io.context,FM_VIDIOCGFREQ,&actual)<0||actual!=(uint32_t)khz*16u)return -1;
 /* GETFREQ is only cached state. Require the hardware completion bit and
  * channel register as well; native audio output still needs separate proof. */
 for(unsigned attempt=0;attempt<6;attempt++){
  unsigned status,channel;
  if(read_register(s,10,&status))return -1;
  if(status&0x4000u){
   if(read_register(s,11,&channel)||(channel&1023u)!=expected)return -1;
   s->last_tuned=khz;s->last_channel=expected;return 0;
  }
  if(attempt<5&&s->io.wait_ms(s->io.context,10)<0)return -1;
 }
 return -1;
}
static int sample(void *context,int *quality){
 struct fm_si470x *s=context;struct fm_v4l_tuner tuner;
 if(!s||!s->verified||!s->last_tuned||!quality)return -1;
 unsigned status,channel;
 if(read_register(s,10,&status)||read_register(s,11,&channel)||(channel&1023u)!=s->last_channel)return -1;
 memset(&tuner,0,sizeof(tuner));
 if(s->io.control(s->io.context,FM_VIDIOCGTUNER,&tuner)<0)return -1;
 /* This driver's signal is a binary station judgement, not a continuous RSSI.
  * Normalization only adapts the core API; callers must not label it RSSI. */
 if(tuner.signal!=0&&tuner.signal!=65535)return -1;
 *quality=tuner.signal?255:0;return tuner.signal?1:0;
}
struct fm_backend fm_si470x_backend(struct fm_si470x *s){return (struct fm_backend){s,tune,sample};}

/* Stock VIDIOCSAUDIO performs the driver's internal ADC-mute on/off sequence.
 * Keep application output muted while using it to leave the driver quiescent,
 * including after an fmSetFreq failure left internal mute bit0x100 set. */
int fm_si470x_quiesce(struct fm_si470x *s){
 if(!s||!s->identity_verified)return -1;
 struct fm_v4l_audio audio;memset(&audio,0,sizeof(audio));
 if(s->io.control(s->io.context,FM_VIDIOCGAUDIO,&audio)<0)return -1;
 audio.flags|=1u;
 if(s->io.control(s->io.context,FM_VIDIOCSAUDIO,&audio)<0)return -1;
 s->last_tuned=0;return 0;
}
