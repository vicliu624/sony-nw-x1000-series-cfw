#include <assert.h>
#include <string.h>
#include "../../runtime/apps/fm-radio/fm_audio.h"
struct audio_fake {int32_t values[5],original[5];int writes,fail_at,fail_get,always_fail_source,analog_volume,silent_at,powerdown,power_read_failed;};
static int audio_control(void *context,uint32_t command,int32_t *value){
 struct audio_fake *f=context;
 if(command==FM_AUDIO_GET_CODEC_POWERDOWN){if(f->power_read_failed)return -1;*value=f->powerdown;return 0;}
 const uint32_t reads[]={FM_AUDIO_GET_MUTE,FM_AUDIO_GET_SOURCE,FM_AUDIO_GET_OUTPUT,FM_AUDIO_GET_PCM,FM_AUDIO_GET_ADC};
 const uint32_t writes[]={FM_AUDIO_SET_MUTE,FM_AUDIO_SET_SOURCE,FM_AUDIO_SET_OUTPUT,FM_AUDIO_SET_PCM,FM_AUDIO_SET_ADC};
 for(int i=0;i<5;i++){
  if(command==reads[i]){if(f->fail_get==i+1)return -1;*value=f->values[i];return 0;}
  if(command==writes[i]){f->writes++;if(f->writes==f->fail_at||(i==1&&f->always_fail_source))return -1;if(f->writes!=f->silent_at){if(i==0)f->values[i]=(f->values[i]&~31)|(*value&31);else f->values[i]=*value;}return 0;}
 }
 assert(0);return -1;
}
static void audio_reset(struct audio_fake *f){memset(f,0,sizeof(*f));int32_t values[]={0,0,1,0x3232,0x2020};memcpy(f->values,values,sizeof(values));memcpy(f->original,values,sizeof(values));f->analog_volume=0x1414;}

#include "../../runtime/apps/fm-radio/fm_session.h"
#include "../../runtime/apps/fm-radio/fm_radio_ui.h"
struct tuner_fake {uint32_t frequency,fail;int wrong_name,wrong_unit,short_band,mismatch,bad_signal,valid,sets,not_done,wrong_channel,config,read_error,waits,cancel,read_error_index,config_writes,drop_write,fail_applied;};
static int tuner_control(void *context,uint32_t request,void *arg){
 struct tuner_fake *f=context;if(f->fail==request)return -1;
 if(request==FM_VIDIOCGCAP){struct fm_v4l_capability *p=arg;memset(p,0,sizeof(*p));strcpy(p->name,f->wrong_name?"Another tuner":"Silicon Labs. Tuner");p->type=2;}
 else if(request==FM_VIDIOCGTUNER){struct fm_v4l_tuner *p=arg;assert(p->tuner==0);memset(p,0,sizeof(*p));strcpy(p->name,"FM");p->low=76000*16;p->high=(f->short_band?90000:108000)*16;p->flags=f->wrong_unit?0:8;p->signal=f->bad_signal?123:f->valid?65535:0;}
 else if(request==FM_VIDIOCSFREQ){f->frequency=*(uint32_t *)arg;f->sets++;}
 else if(request==FM_VIDIOCGFREQ)*(uint32_t *)arg=f->frequency+(f->mismatch?16:0);
 else if(request==FM_VIDIOC_GETREG){struct fm_v4l_register *p=arg;assert(p->index<=11);
  unsigned value=p->index==5?(unsigned)(f->config?f->config:0x50):p->index==10?(f->not_done?0:0x4000):((f->frequency/16-(((unsigned)(f->config?f->config:0x50)&0xc0u)?76000u:87500u))/(((unsigned)(f->config?f->config:0x50)&0x30u)==0?200u:((unsigned)(f->config?f->config:0x50)&0x30u)==0x10u?100u:50u))+(f->wrong_channel?1:0);
  p->values[p->index]=(f->read_error||f->read_error_index==(int)p->index)?65535:value;
 }
 else if(request==FM_VIDIOC_PUTREG){struct fm_v4l_write_register *p=arg;assert(p->index==5&&!p->reserved);f->config_writes++;if(!f->drop_write)f->config=p->value;if(f->fail_applied){f->fail_applied=0;return -1;}}
 else if(request==FM_VIDIOCGAUDIO){struct fm_v4l_audio *p=arg;memset(p,0,sizeof(*p));p->mode=2;}
 else if(request==FM_VIDIOCSAUDIO){struct fm_v4l_audio *p=arg;assert(p->audio==0&&(p->flags&1)&&p->mode==2);}
 else assert(0);
 return 0;
}
static int wait_ms(void *p,unsigned ms){struct tuner_fake *f=p;assert(ms==10);f->waits++;return f->cancel?-1:0;}

struct platform {struct audio_fake audio;struct tuner_fake tuner;int audio_open,tuner_open,fail_audio,fail_tuner,fail_close;};
static int open_audio(void *p,struct fm_audio_transport *out){struct platform *f=p;assert(!f->audio_open&&!f->tuner_open);if(f->fail_audio)return -1;f->audio_open=1;*out=(struct fm_audio_transport){&f->audio,audio_control};return 0;}
static int close_audio(void *p){struct platform *f=p;assert(f->audio_open&&!f->tuner_open);f->audio_open=0;return 0;}
static int open_tuner(void *p,struct fm_tuner_transport *out){struct platform *f=p;assert(f->audio_open&&f->audio.values[0]==31);if(f->fail_tuner)return -1;f->tuner_open=1;*out=(struct fm_tuner_transport){&f->tuner,tuner_control,wait_ms};return 0;}
static int close_tuner(void *p){struct platform *f=p;assert(f->tuner_open&&f->audio.values[0]==31);f->tuner_open=0;return f->fail_close?-1:0;}
int main(void){
 struct platform f={0};struct fm_session s={0};audio_reset(&f.audio);
 struct fm_session_ops ops={&f,open_audio,close_audio,open_tuner,close_tuner,0};struct fm_band band={76000,90000,100};
 assert(!fm_session_start(&s,ops,band,82500)&&s.active&&f.audio.values[0]==2);
 struct fm_ui ui;fm_ui_init(&ui,&s.radio);fm_ui_tap(&ui,180,180);assert(s.radio.frequency==82600&&f.tuner.frequency==82600*16);
 fm_ui_tap(&ui,40,280);assert(s.radio.favorite_count==1);
 fm_ui_tap(&ui,40,230);assert(s.radio.scanning);
 assert(!fm_session_update_audio(&s)&&!s.audio.playing&&f.audio.values[0]==31);
 fm_ui_tap(&ui,40,230);assert(!s.radio.scanning);
 assert(!fm_session_update_audio(&s)&&s.audio.playing&&f.audio.values[0]==2);
 s.radio.error=1;assert(!fm_session_update_audio(&s)&&!s.audio.playing&&f.audio.values[0]==31);
 assert(!fm_tune(&s.radio,82600)&&!fm_session_update_audio(&s)&&s.audio.playing);
 fm_ui_tap(&ui,40,230);assert(s.radio.scanning);assert(!fm_session_update_audio(&s));int sets=f.tuner.sets;
 assert(!fm_session_stop(&s)&&!s.active&&!s.radio.scanning&&!f.audio_open&&!f.tuner_open&&f.tuner.sets==sets);
 assert(!memcmp(f.audio.values,f.audio.original,sizeof(f.audio.values)));assert(!fm_session_stop(&s));
 f.tuner.config=0x1ca0;assert(!fm_session_start(&s,ops,(struct fm_band){76000,108000,100},108000)&&f.tuner.config==0x1c60);
 assert(!fm_session_stop(&s)&&f.tuner.config==0x1ca0);f.tuner.config=0;
 f.fail_audio=1;assert(fm_session_start(&s,ops,band,82500)<0&&!f.audio_open);f.fail_audio=0;
 f.fail_tuner=1;assert(fm_session_start(&s,ops,band,82500)<0&&!f.audio_open&&!f.tuner_open&&!memcmp(f.audio.values,f.audio.original,sizeof(f.audio.values)));f.fail_tuner=0;
 f.tuner.not_done=1;assert(fm_session_start(&s,ops,band,82500)<0&&!f.audio_open&&!f.tuner_open);f.tuner.not_done=0;
 assert(!fm_session_start(&s,ops,band,82500));f.audio.always_fail_source=1;
 assert(fm_session_stop(&s)<0&&s.audio_open&&!s.tuner_open&&s.audio.dirty&&f.audio.values[0]==31);
 assert(fm_session_start(&s,ops,band,82500)<0);f.audio.always_fail_source=0;assert(!fm_session_stop(&s)&&!s.audio_open);
 assert(!fm_session_start(&s,ops,band,82500));f.tuner.fail=FM_VIDIOCGAUDIO;
 assert(fm_session_stop(&s)<0&&s.tuner_open&&s.audio_open&&!s.active&&f.audio.values[0]==31);
 assert(fm_session_start(&s,ops,band,82500)<0);f.tuner.fail=0;
 assert(!fm_session_stop(&s)&&!s.tuner_open&&!s.audio_open);
 assert(!fm_session_start(&s,ops,band,82500));f.fail_close=1;assert(fm_session_stop(&s)<0&&s.close_failed&&!s.audio_open&&!s.tuner_open);
 assert(fm_session_start(&s,ops,band,82500)<0);
 return 0;
}
