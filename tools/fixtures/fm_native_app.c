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

#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include "../../runtime/apps/fm-radio/fm_storage.h"
#include "../../runtime/apps/fm-radio/fm_posix.h"
#include "../../runtime/native/linux_devices.h"
int hb_fm_native_review(void);
int hb_fm_main(int,char **);
static struct audio_fake audio;static struct tuner_fake tuner;
static volatile int *stop_requested;
static int mode,event,audio_open,tuner_open,gfx_open,closes,frames,live_unmutes,quiesce_failed_once,storage_lease=1;
static int storage_guard(void *p){(void)p;return storage_lease?0:-1;}
int __wrap_fm_storage_open(struct fm_storage *s){
 if(mode!=0&&mode<11)return FM_STORAGE_BOUNDARY;
 int fd=open("work/fm-radio-review/native-state",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return FM_STORAGE_IO;
 int rc=fm_storage_bind(s,fd,storage_guard,0);assert(!close(fd));return rc;
}
int hb_stop_signals_install(volatile int *stop){stop_requested=stop;return 0;}
int fm_os_open(const char *name,int flags){
 if(!strcmp(name,"/dev/sound/mixer")){assert(flags==2&&!audio_open&&!tuner_open);if(mode==1)return -1;audio_open=1;return 40;}
 assert(!strcmp(name,"/dev/v4l/radio0")&&flags==0&&audio_open&&!tuner_open&&audio.values[0]==31);
 if(mode==2)return -1;
 tuner_open=1;audio.values[0]|=0x100;return 41;
}
int fm_os_close(int fd){
 closes++;
 if(fd==40){assert(audio_open&&!tuner_open);audio_open=0;return 0;}
 assert(fd==41&&tuner_open&&audio.values[0]==31);if(mode==0||mode==11)assert(tuner.config==0x1ca0);tuner_open=0;return 0;
}
int fm_os_ioctl(int fd,unsigned long command,void *value){
 if(fd==40){assert(audio_open);if(command==FM_AUDIO_SET_MUTE&&*(int32_t *)value==2)live_unmutes++;return audio_control(&audio,(uint32_t)command,value);}
 assert(fd==41&&tuner_open);
 if(mode==9&&command==FM_VIDIOCGAUDIO&&!quiesce_failed_once){quiesce_failed_once=1;return -1;}
 int result=tuner_control(&tuner,(uint32_t)command,value);
 if(command==FM_VIDIOCSFREQ){if(tuner.not_done)audio.values[0]|=0x100;else audio.values[0]&=~0x100;}
 if(command==FM_VIDIOCSAUDIO&&!result)audio.values[0]&=~0x100;
 if(mode==12&&command==FM_VIDIOCSFREQ&&tuner.sets>1)storage_lease=0;
 if(mode==8&&command==FM_VIDIOCSFREQ)*stop_requested=1;
 return result;
}
int fm_os_usleep(unsigned duration){assert(duration==10000);return 0;}
int hb_devices_open(struct hb_devices *d,const unsigned short *p,unsigned n,volatile int *stop){
 assert(n==HB_DISPLAY_PIXELS&&p[0]);
 if(audio_open)assert(tuner_open&&audio.values[0]==2);else assert(!tuner_open);
 if(mode==11||mode==13)assert(tuner.frequency==76100*16);
 *d=(struct hb_devices){0};d->surface=p;d->stop=stop;if(mode==4)return -1;gfx_open=1;return 0;
}
int hb_devices_close(struct hb_devices *d){(void)d;assert(gfx_open&&(!audio_open||audio.values[0]==31));gfx_open=0;return 0;}
void hb_devices_present(struct hb_devices *d){
 frames++;if(mode==0&&frames==1){FILE *f=fopen("work/fm-radio-review/native-main.rgb565","wb");assert(f);assert(fwrite(d->surface,2,HB_DISPLAY_PIXELS,f)==HB_DISPLAY_PIXELS);assert(!fclose(f));}
}
void hb_devices_flush(struct hb_devices *d){(void)d;if(mode==5)*stop_requested=1;}
int hb_devices_next_touch(struct hb_devices *d,unsigned char p[11],int timeout){
 (void)d;assert(timeout==50);if(*stop_requested)return -1;if(mode==6)return -2;
 assert(event<((mode==11||mode==13)?2:10));unsigned x=event<2?180:40;unsigned y=event<2?180:event<4?280:event<8?230:400;
 if(mode==11||mode==13){x=40;y=400;}
 unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
 memset(p,0,11);p[1]=event%2==0;p[2]=rx>>8;p[3]=rx;p[4]=ry>>8;p[5]=ry;
 if(mode==7&&event==9)audio.fail_at=audio.writes+3;
 event++;return 1;
}
int main(void){
 if(mkdir("work/fm-radio-review/native-state",0700))assert(errno==EEXIST);
 const char *owned[]={"work/fm-radio-review/native-state/state-a.bin","work/fm-radio-review/native-state/state-b.bin","work/fm-radio-review/native-state/state.tmp"};
 for(unsigned i=0;i<3;i++)if(unlink(owned[i]))assert(errno==ENOENT);
 for(mode=0;mode<=13;mode++){
  audio_reset(&audio);memset(&tuner,0,sizeof(tuner));event=audio_open=tuner_open=gfx_open=closes=frames=live_unmutes=quiesce_failed_once=0;
  storage_lease=1;
  if(mode==0||mode==11)tuner.config=0x1ca0;
  if(mode==3)tuner.not_done=1;
  if(mode==10)audio.values[0]=audio.original[0]=0x100;
  char *arguments[]={"app","--native",0};int result=hb_fm_main(mode==11?2:1,arguments);
  assert(result==(mode==12?4:(mode==0||mode==5||mode==11||mode==13)?0:2));
  assert(!audio_open&&!tuner_open&&!gfx_open);
  assert(!memcmp(audio.values,audio.original,sizeof(audio.values)));
  if(mode==0)assert(event==10&&frames>=5&&live_unmutes==2&&tuner.sets>2);
  if(mode==8)assert(!live_unmutes&&!frames);
 }
 for(unsigned i=0;i<3;i++)if(unlink(owned[i]))assert(errno==ENOENT);
 assert(!rmdir("work/fm-radio-review/native-state"));
 return 0;
}
