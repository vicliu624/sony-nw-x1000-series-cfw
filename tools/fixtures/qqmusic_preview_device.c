#include "../../runtime/apps/qqmusic/qqmusic_preview_device.h"
#include "../../runtime/apps/fm-radio/fm_audio.h"
#include <assert.h>
#include <string.h>
#include <errno.h>
struct model {
 struct qq_preview_audio_state state,original;
 unsigned approved,guard,mixer,pcm,pcm_ioctls,reset,closes,guard_drops,accepted,backpressure,exited;
 unsigned calls,fail_at;int wrong_identity,wrong_rate,restore_source_fail,close_ambiguous;
 unsigned padding_mode,padding_bytes,delay_calls;int32_t block_size,delay;
};
static struct model m;static struct qq_preview_device d;static struct qq_preview_session s;static uint64_t now;
static int preflight(void *p,uint64_t g){struct model *v=p;assert(g);return v->approved?0:-1;}
static int retain(void *p){struct model *v=p;v->guard=1;return 9;}
static int drop(void *p,int fd){struct model *v=p;assert(fd==9&&v->guard&&!v->mixer&&!v->pcm);v->guard=0;v->guard_drops++;return 0;}
static int open_device(void *p,const char *name,int flags){struct model *v=p;assert(v->approved&&v->guard);
 if(!strcmp(name,"/dev/sound/mixer")){assert(flags==2&&!v->mixer);v->mixer=1;return 10;}
 assert(!strcmp(name,"/dev/sound/dsp")&&flags==0x801&&!v->pcm);v->pcm=1;return 11;
}
static int identity(void *p,int fd,unsigned major,unsigned minor){struct model *v=p;assert(major==14&&((fd==10&&minor==0)||(fd==11&&minor==3)));return fd==11&&v->wrong_identity?-1:0;}
static int close_device(void *p,int fd){struct model *v=p;v->closes++;if(fd==11){assert(v->pcm);v->pcm=0;if(v->close_ambiguous)return -EINTR;}else{assert(fd==10&&v->mixer);v->mixer=0;}return 0;}
static int control(void *p,int fd,uint32_t cmd,int32_t *value){
 struct model *v=p;int32_t *target=0;v->calls++;if(v->fail_at&&v->calls==v->fail_at)return -EIO;
 if(fd==11){assert(v->pcm&&!v->wrong_identity);v->pcm_ioctls++;
  if(cmd==0x5000){v->reset++;return 0;}
  assert(value);
  if(cmd==0xc0045004u){v->padding_mode=1;*value=v->block_size;return 0;}
  if(cmd==0x80045017u){v->delay_calls++;*value=v->delay;return 0;}
  if(cmd==0xc0045005u){assert(*value==16);return 0;}
  if(cmd==0xc0045006u){assert(*value==2);return 0;}
  assert(cmd==0xc0045002u&&*value==44100);if(v->wrong_rate)*value=22050;return 0;
 }
 assert(fd==10&&v->mixer&&value);
 switch(cmd){
 case FM_AUDIO_GET_MUTE:*value=v->state.mute;return 0;
 case FM_AUDIO_GET_SOURCE:*value=v->state.source;return 0;
 case FM_AUDIO_GET_OUTPUT:*value=v->state.output;return 0;
 case FM_AUDIO_GET_PCM:*value=v->state.pcm_mix;return 0;
 case FM_AUDIO_GET_ADC:*value=v->state.adc_mix;return 0;
 case FM_AUDIO_GET_CODEC_POWERDOWN:*value=v->state.powerdown;return 0;
 case FM_AUDIO_SET_MUTE:assert(*value>=0&&*value<=31);v->state.mute=(v->state.mute&~31)|*value;return 0;
 case FM_AUDIO_SET_SOURCE:if(v->restore_source_fail&&*value==v->original.source)return 0;target=&v->state.source;break;
 case FM_AUDIO_SET_OUTPUT:target=&v->state.output;break;
 case FM_AUDIO_SET_PCM:target=&v->state.pcm_mix;break;
 case FM_AUDIO_SET_ADC:target=&v->state.adc_mix;break;
 case 0x4004610du:assert(*value==0||*value==1);v->state.mute=31;target=&v->state.powerdown;break;
 default:assert(0);
 }
 *target=*value;return 0;
}
static int write_pcm(void *p,int fd,const unsigned char *data,unsigned n){struct model *v=p;unsigned take=n,i;assert(v->pcm&&fd==11&&n);if(v->backpressure){v->backpressure--;return -EAGAIN;}if(take>7)take=7;for(i=0;i<take;i++)assert(data[i]==(v->padding_mode?0:(unsigned char)(v->accepted+i)));if(v->padding_mode)v->padding_bytes+=take;else v->accepted+=take;return (int)take;}
static int exited(void *p,uint64_t g){assert(g);return ((struct model *)p)->exited?1:0;}
static void setup(void){
 struct qq_preview_device_io io={&m,preflight,retain,drop,open_device,identity,close_device,control,write_pcm,exited};
 memset(&m,0,sizeof(m));m.block_size=1024;m.approved=m.exited=1;m.original.source=2;m.original.output=1;m.original.pcm_mix=0x3232;m.original.adc_mix=0x2020;m.original.powerdown=1;m.state=m.original;now=100;
 assert(!qq_preview_device_init(&d,&io));assert(!qq_preview_session_init(&s,qq_preview_device_operations(&d)));assert(!qq_preview_session_begin(&s,now));
}
static int poll_session(void){now+=20;return qq_preview_session_poll(&s,now);}
static void ready(void){unsigned i;assert(!poll_session()&&s.phase==QQ_PREVIEW_LEASED);assert(qq_preview_session_format(&s,44100,2)==1);for(i=0;i<20&&s.phase==QQ_PREVIEW_CONFIGURING;i++)assert(poll_session()>=0);assert(s.phase==QQ_PREVIEW_READY);}
static void finish(void){unsigned i;for(i=0;i<40&&s.phase!=QQ_PREVIEW_DONE&&s.phase!=QQ_PREVIEW_REVIEW;i++)(void)poll_session();}
static void restored(void){assert(s.phase==QQ_PREVIEW_DONE&&!m.guard&&!m.pcm&&!m.mixer);assert(!memcmp(&m.state,&m.original,sizeof(m.state)));}
int main(void){
 unsigned i,used,before;unsigned char pcm[32];
 for(i=0;i<sizeof(pcm);i++)pcm[i]=(unsigned char)i;
 setup();ready();before=m.calls;assert(!qq_preview_device_drain(&d,s.generation,now)&&m.calls==before);assert(qq_preview_session_write(&s,pcm,4)<0);assert(qq_preview_session_stop(&s,now)==1);finish();restored();
 setup();ready();for(used=0;used<sizeof(pcm);){int got=qq_preview_session_write(&s,pcm+used,sizeof(pcm)-used);assert(got>0);used+=(unsigned)got;}
 assert(qq_preview_device_drain(&d,s.generation+1,now)<0&&!d.draining);
 assert(qq_preview_device_drain(&d,s.generation,now)==1&&d.drain_padding==992);assert(qq_preview_session_write(&s,pcm,4)<0);
 m.backpressure=1;assert(qq_preview_device_drain(&d,s.generation,now)==1&&!m.padding_bytes);
 for(i=0;i<200&&d.drain_padding;i++){now++;assert(qq_preview_device_drain(&d,s.generation,now)==1);}
 assert(m.padding_bytes==992&&m.accepted==32&&!m.delay_calls);m.delay=512;assert(qq_preview_device_drain(&d,s.generation,++now)==1);m.delay=0;assert(!qq_preview_device_drain(&d,s.generation,++now));assert(!qq_preview_device_drain(&d,s.generation,now+20000));assert(qq_preview_session_stop(&s,now)==1);finish();restored();
 setup();ready();assert(qq_preview_session_write(&s,pcm,4)==4);m.block_size=0;assert(qq_preview_device_drain(&d,s.generation,now)<0&&d.drain_failed);assert(qq_preview_session_stop(&s,now)==1);finish();restored();
 setup();ready();assert(qq_preview_session_write(&s,pcm,4)==4);assert(qq_preview_device_drain(&d,s.generation,now)==1);assert(qq_preview_device_drain(&d,s.generation,now+10000)<0);assert(qq_preview_session_stop(&s,now)==1);finish();restored();
 setup();ready();assert(qq_preview_session_write(&s,pcm,4)==4);assert(qq_preview_device_drain(&d,s.generation,now)==1);assert(qq_preview_session_stop(&s,now)==1);finish();restored();assert(!m.padding_bytes&&!m.delay_calls);
 setup();ready();assert(qq_preview_session_write(&s,pcm,7)==7);before=m.calls;assert(qq_preview_device_drain(&d,s.generation,now)<0&&m.calls==before);assert(qq_preview_session_stop(&s,now)==1);finish();restored();
 setup();assert(!poll_session()&&s.phase==QQ_PREVIEW_LEASED);assert(qq_preview_session_stop(&s,now)==1);finish();restored();assert(!m.pcm_ioctls);
 setup();ready();m.backpressure=1;assert(!qq_preview_session_write(&s,pcm,sizeof(pcm))&&s.phase==QQ_PREVIEW_READY);
 for(used=0;used<sizeof(pcm);){int got=qq_preview_session_write(&s,pcm+used,sizeof(pcm)-used);assert(got>0);used+=(unsigned)got;}
 assert(s.phase==QQ_PREVIEW_PLAYING&&m.state.mute==9);m.exited=0;before=m.reset;assert(qq_preview_session_stop(&s,now)==1);assert(poll_session()==1&&m.state.mute==31);assert(poll_session()==1&&m.reset==before&&m.pcm);m.exited=1;finish();restored();
 assert(!qq_preview_session_begin(&s,now));ready();assert(qq_preview_session_stop(&s,now)==1);finish();restored();
 setup();ready();assert(qq_preview_session_write(&s,pcm,sizeof(pcm))>0);m.fail_at=m.calls+2;assert(qq_preview_session_stop(&s,now)==1);finish();restored();assert(s.failed&&d.stop_mute_failed&&m.reset>=2);
 setup();m.approved=0;assert(poll_session()<0&&!m.guard&&!m.mixer&&!m.pcm);finish();assert(s.phase==QQ_PREVIEW_DONE&&s.failed&&!m.guard);
 setup();assert(!poll_session());m.wrong_identity=1;assert(qq_preview_session_format(&s,44100,2)<0);finish();restored();assert(!m.pcm_ioctls&&s.failed);
 setup();assert(!poll_session());m.wrong_rate=1;assert(qq_preview_session_format(&s,44100,2)==1);finish();restored();assert(s.failed);
 setup();ready();m.restore_source_fail=1;assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_REVIEW&&m.guard&&!m.pcm&&m.mixer&&m.state.mute==31&&!m.guard_drops);
 setup();ready();m.close_ambiguous=1;assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_REVIEW&&m.guard&&d.uncertain);before=m.closes;assert(poll_session()<0&&m.closes==before&&qq_preview_session_begin(&s,now)<0);
 /* A single failed setup/control call must either cleanly restore or retain
  * the guard. Never claim success with an open PCM or mutated route. */
 for(i=1;i<=35;i++){
  setup();m.fail_at=i;(void)poll_session();if(s.phase==QQ_PREVIEW_LEASED)(void)qq_preview_session_format(&s,44100,2);
  {unsigned n;for(n=0;n<20&&s.phase==QQ_PREVIEW_CONFIGURING;n++)(void)poll_session();}
  if(s.phase==QQ_PREVIEW_READY)(void)qq_preview_session_stop(&s,now);
  finish();
  if(s.phase==QQ_PREVIEW_DONE)restored();else assert(s.phase==QQ_PREVIEW_REVIEW&&m.guard);
 }
 return 0;
}
