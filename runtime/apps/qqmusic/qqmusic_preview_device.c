#include "qqmusic_preview_device.h"
#include "../fm-radio/fm_audio.h"
#include <string.h>
#include <errno.h>
#define PCM_RESET 0x5000u
#define PCM_FORMAT 0xc0045005u
#define PCM_CHANNELS 0xc0045006u
#define PCM_RATE 0xc0045002u
#define POWER_SET 0x4004610du
static int read_state(void *context,struct qq_preview_audio_state *out){
 struct qq_preview_device *d=context;int32_t values[6];unsigned i;
 static const uint32_t gets[]={FM_AUDIO_GET_MUTE,FM_AUDIO_GET_SOURCE,FM_AUDIO_GET_OUTPUT,FM_AUDIO_GET_PCM,FM_AUDIO_GET_ADC,FM_AUDIO_GET_CODEC_POWERDOWN};
 if(!d||!out||d->mixer<0)return -1;
 memset(out,0,sizeof(*out));
 for(i=0;i<6;i++){values[i]=0;if(d->io.control(d->io.context,d->mixer,gets[i],&values[i]))return -1;}
 out->mute=values[0];out->source=values[1];out->output=values[2];out->pcm_mix=values[3];out->adc_mix=values[4];out->powerdown=values[5];
 /* These are actual negotiation results, not SPEED0 "queries". */
 out->format=d->format;out->rate=d->rate;out->channels=d->channels;
 if(!d->captured){d->initial=*out;d->captured=1;}
 return 0;
}
static int setting(struct qq_preview_device *d,uint32_t set,uint32_t get,int32_t wanted){
 int32_t value=wanted,actual=0;
 if(d->mixer<0||d->io.control(d->io.context,d->mixer,get,&actual))return -1;
 if(set==FM_AUDIO_SET_MUTE?((actual&31)==wanted):(actual==wanted))return 0;
 if(d->io.control(d->io.context,d->mixer,set,&value)||d->io.control(d->io.context,d->mixer,get,&actual))return -1;
 return set==FM_AUDIO_SET_MUTE?((actual&31)==wanted?0:-1):(actual==wanted?0:-1);
}
static int acquire(void *context,uint64_t generation){
 struct qq_preview_device *d=context;int rc;
 if(!d||!d->initialized||!generation||d->uncertain)return -1;
 if(d->acquired)return d->generation==generation?0:-1;
 if(d->guard>=0||d->mixer>=0||d->pcm>=0)return -1;
 if(d->generation!=generation){
  if(d->generation>=generation)return -1;
  d->generation=generation;d->captured=d->configure_started=d->configure_step=d->restore_step=d->stopping=d->pcm_verified=d->stop_muted=d->stop_mute_failed=d->reset_confirmed=d->closed_confirmed=d->restore_failed=0;
  d->format=d->rate=d->channels=0;memset(&d->initial,0,sizeof(d->initial));
  d->accepted_bytes=d->drain_last_ms=d->drain_deadline_ms=0;
  d->draining=d->drain_block=d->drain_padding=d->drain_done=d->drain_failed=0;
 }
 rc=d->io.preflight(d->io.context,generation);if(rc)return rc==1?1:-1;
 d->generation=generation;d->guard=d->io.retain_guard(d->io.context);if(d->guard<0)return -1;
 d->mixer=d->io.open(d->io.context,"/dev/sound/mixer",2);
 if(d->mixer<0||d->io.identity(d->io.context,d->mixer,14,0))return -1;
 d->acquired=1;return 0;
}
static int negotiate(struct qq_preview_device *d,uint32_t request,int32_t wanted,int32_t *result){
 int32_t value=wanted;
 if(d->pcm<0||d->io.control(d->io.context,d->pcm,request,&value)||value!=wanted)return -1;
 *result=value;return 0;
}
static int configure(void *context,unsigned rate,unsigned channels){
 struct qq_preview_device *d=context;int rc=0;
 if(!d||!d->acquired||!d->captured||d->stopping||d->uncertain||rate!=44100||channels!=2)return -1;
 d->configure_started=1;
 switch(d->configure_step){
 case 0:
  d->pcm=d->io.open(d->io.context,"/dev/sound/dsp",0x801);
  if(d->pcm<0||d->io.identity(d->io.context,d->pcm,14,3))return -1;
  d->pcm_verified=1;break;
 case 1:rc=setting(d,FM_AUDIO_SET_MUTE,FM_AUDIO_GET_MUTE,31);break;
 case 2:rc=setting(d,POWER_SET,FM_AUDIO_GET_CODEC_POWERDOWN,0);break;
 case 3:rc=d->io.control(d->io.context,d->pcm,PCM_RESET,0);break;
 case 4:rc=negotiate(d,PCM_FORMAT,16,&d->format);break;
 case 5:rc=negotiate(d,PCM_CHANNELS,2,&d->channels);break;
 case 6:rc=negotiate(d,PCM_RATE,44100,&d->rate);break;
 case 7:rc=setting(d,FM_AUDIO_SET_PCM,FM_AUDIO_GET_PCM,0x6464);break;
 case 8:rc=setting(d,FM_AUDIO_SET_ADC,FM_AUDIO_GET_ADC,0);break;
 case 9:rc=setting(d,FM_AUDIO_SET_SOURCE,FM_AUDIO_GET_SOURCE,0);break;
 case 10:rc=setting(d,FM_AUDIO_SET_OUTPUT,FM_AUDIO_GET_OUTPUT,0);break;
 default:return 0;
 }
 if(rc)return -1;
 d->configure_step++;return d->configure_step==11?0:1;
}
static int write_pcm(void *context,const unsigned char *data,unsigned n){
 struct qq_preview_device *d=context;int rc;
 if(!d||!data||!n||n>4096||d->configure_step!=11||d->pcm<0||d->stopping||d->uncertain||d->draining)return -1;
 rc=d->io.write(d->io.context,d->pcm,data,n);
 if(rc==-EINTR||rc==-EAGAIN||rc==-EWOULDBLOCK)return 0;
 if(rc>0&&(unsigned)rc<=n){d->accepted_bytes+=(unsigned)rc;return rc;}return -1;
}
int qq_preview_device_drain(struct qq_preview_device *d,uint64_t generation,uint64_t now){
 static const unsigned char silence[4096]={0};int32_t value=0;int rc;unsigned wanted;
 if(!d||!d->initialized||!generation||generation!=d->generation||d->configure_step!=11||!d->pcm_verified||d->pcm<0||d->stopping||d->uncertain||d->drain_failed)return -1;
 if(!d->draining){
  d->draining=1;d->drain_last_ms=now;
  if(now>UINT64_MAX-10000u||d->accepted_bytes%4u){d->drain_failed=1;return -1;}
  d->drain_deadline_ms=now+10000u;
  if(!d->accepted_bytes){d->drain_done=1;return 0;}
  /* First successful write guarantees the original fragment array exists. */
  if(d->io.control(d->io.context,d->pcm,0xc0045004u,&value)||value<128||value>65536||(value&3)){d->drain_failed=1;return -1;}
  d->drain_block=(unsigned)value;d->drain_padding=(unsigned)((value-d->accepted_bytes%(unsigned)value)%(unsigned)value);return 1;
 }
 if(d->drain_done)return 0;
 if(now<d->drain_last_ms||now>=d->drain_deadline_ms){d->drain_failed=1;return -1;}d->drain_last_ms=now;
 if(d->drain_padding){
  wanted=d->drain_padding>sizeof(silence)?sizeof(silence):d->drain_padding;
  rc=d->io.write(d->io.context,d->pcm,silence,wanted);
  if(rc==-EINTR||rc==-EAGAIN||rc==-EWOULDBLOCK||rc==0)return 1;
  if(rc<0||(unsigned)rc>wanted){d->drain_failed=1;return -1;}
  d->drain_padding-=(unsigned)rc;return 1;
 }
 rc=d->io.control(d->io.context,d->pcm,0x80045017u,&value);
 if(rc==-EINTR||rc==-EAGAIN||rc==-EWOULDBLOCK)return 1;
 if(rc||value<0||value>8*1024*1024){d->drain_failed=1;return -1;}
 if(!value){d->drain_done=1;return 0;}return 1;
}
static int mute(void *context,int32_t value){struct qq_preview_device *d=context;if(!d||d->stopping||value!=9)return -1;return setting(d,FM_AUDIO_SET_MUTE,FM_AUDIO_GET_MUTE,value);}
static int stop(void *context,uint64_t generation,struct qq_preview_stop_receipt *receipt){
 struct qq_preview_device *d=context;int rc;
 if(!d||!receipt||d->uncertain||(d->generation&&generation!=d->generation))return -1;
 memset(receipt,0,sizeof(*receipt));d->stopping=1;
 if(d->captured&&d->configure_started&&!d->stop_muted){if(setting(d,FM_AUDIO_SET_MUTE,FM_AUDIO_GET_MUTE,31))d->stop_mute_failed=1;d->stop_muted=1;return 1;}
 rc=d->io.producer_exited(d->io.context,generation);if(rc==0)return 1;if(rc!=1)return -1;
 if(d->pcm>=0&&d->pcm_verified&&!d->reset_confirmed){
  rc=d->io.control(d->io.context,d->pcm,PCM_RESET,0);
  if(rc){d->uncertain=1;return -1;}d->reset_confirmed=1;return 1;
 }
 if(d->pcm>=0){int fd=d->pcm;d->pcm=-1;
  /* Never retry a possibly consumed fd after close/EINTR. */
  if(d->io.close(d->io.context,fd)){d->uncertain=1;return -1;}
  d->closed_confirmed=1;d->format=d->rate=d->channels=0;return 1;
 }
 receipt->generation=generation;receipt->producer_exited=receipt->pcm_reset=receipt->pcm_closed=1;receipt->had_error=d->stop_mute_failed;return 0;
}
static int restore(void *context,const struct qq_preview_audio_state *saved){
 struct qq_preview_device *d=context;int rc=0;struct qq_preview_audio_state actual;
 if(!d||!saved||d->uncertain||!d->stopping||d->pcm>=0||!d->captured)return -1;
 if(saved->mute!=d->initial.mute||saved->source!=d->initial.source||saved->output!=d->initial.output||saved->pcm_mix!=d->initial.pcm_mix||saved->adc_mix!=d->initial.adc_mix||saved->powerdown!=d->initial.powerdown)return -1;
 if(!d->configure_started)return 0;
 switch(d->restore_step){
 case 0:rc=setting(d,FM_AUDIO_SET_MUTE,FM_AUDIO_GET_MUTE,31);break;
 case 1:rc=setting(d,FM_AUDIO_SET_OUTPUT,FM_AUDIO_GET_OUTPUT,saved->output);break;
 case 2:rc=setting(d,FM_AUDIO_SET_SOURCE,FM_AUDIO_GET_SOURCE,saved->source);break;
 case 3:rc=setting(d,FM_AUDIO_SET_PCM,FM_AUDIO_GET_PCM,saved->pcm_mix);break;
 case 4:rc=setting(d,FM_AUDIO_SET_ADC,FM_AUDIO_GET_ADC,saved->adc_mix);break;
 case 5:rc=setting(d,POWER_SET,FM_AUDIO_GET_CODEC_POWERDOWN,saved->powerdown);break;
 case 6:
  if(read_state(d,&actual)||(actual.mute&~31)!=(saved->mute&~31))d->restore_failed=1;
  if(d->restore_failed){(void)setting(d,FM_AUDIO_SET_MUTE,FM_AUDIO_GET_MUTE,31);return -1;}
  rc=setting(d,FM_AUDIO_SET_MUTE,FM_AUDIO_GET_MUTE,saved->mute&31);break;
 default:return d->restore_failed?-1:0;
 }
 if(rc)d->restore_failed=1;
 d->restore_step++;return d->restore_step==7?(d->restore_failed?-1:0):1;
}
static int release(void *context,uint64_t generation){
 struct qq_preview_device *d=context;
 if(!d||!d->stopping||d->uncertain||d->pcm>=0||(d->generation&&d->generation!=generation))return -1;
 if(d->mixer>=0){int fd=d->mixer;d->mixer=-1;if(d->io.close(d->io.context,fd)){d->uncertain=1;return -1;}return 1;}
 if(d->guard>=0){int fd=d->guard;d->guard=-1;if(d->io.drop_guard(d->io.context,fd)){d->uncertain=1;return -1;}}
 d->acquired=0;return 0;
}
int qq_preview_device_init(struct qq_preview_device *d,const struct qq_preview_device_io *io){
 if(!d||!io||!io->preflight||!io->retain_guard||!io->drop_guard||!io->open||!io->identity||!io->close||!io->control||!io->write||!io->producer_exited)return -1;
 memset(d,0,sizeof(*d));d->io=*io;d->guard=d->mixer=d->pcm=-1;d->initialized=1;
 d->operations.context=d;d->operations.acquire=acquire;d->operations.read_state=read_state;d->operations.configure=configure;d->operations.write=write_pcm;d->operations.mute=mute;d->operations.stop=stop;d->operations.restore=restore;d->operations.release=release;return 0;
}
const struct qq_preview_session_ops *qq_preview_device_operations(struct qq_preview_device *d){return d&&d->initialized?&d->operations:0;}
