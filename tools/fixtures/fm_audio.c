#include <assert.h>
#include <string.h>
#include "../../runtime/apps/fm-radio/fm_audio.h"
struct fake {int32_t values[5],original[5];int writes,fail_at,fail_get,always_fail_source,analog_volume,silent_at,powerdown,power_read_failed;};
static int control(void *context,uint32_t command,int32_t *value){
 struct fake *f=context;
 if(command==FM_AUDIO_GET_CODEC_POWERDOWN){if(f->power_read_failed)return -1;*value=f->powerdown;return 0;}
 const uint32_t reads[]={FM_AUDIO_GET_MUTE,FM_AUDIO_GET_SOURCE,FM_AUDIO_GET_OUTPUT,FM_AUDIO_GET_PCM,FM_AUDIO_GET_ADC};
 const uint32_t writes[]={FM_AUDIO_SET_MUTE,FM_AUDIO_SET_SOURCE,FM_AUDIO_SET_OUTPUT,FM_AUDIO_SET_PCM,FM_AUDIO_SET_ADC};
 for(int i=0;i<5;i++){
  if(command==reads[i]){if(f->fail_get==i+1)return -1;*value=f->values[i];return 0;}
  if(command==writes[i]){f->writes++;if(f->writes==f->fail_at||(i==1&&f->always_fail_source))return -1;if(f->writes!=f->silent_at){if(i==0)f->values[i]=(f->values[i]&~31)|(*value&31);else f->values[i]=*value;}return 0;}
 }
 assert(0);return -1;
}
static void reset(struct fake *f){memset(f,0,sizeof(*f));int32_t values[]={0,0,1,0x3232,0x2020};memcpy(f->values,values,sizeof(values));memcpy(f->original,values,sizeof(values));f->analog_volume=0x1414;}
int main(void){
 struct fake f;struct fm_audio a={0};reset(&f);
 struct fm_audio_transport io={&f,control};
 assert(!fm_audio_prepare(&a,io)&&a.dirty&&!a.playing&&f.values[0]==31&&f.values[1]==2&&f.values[2]==0&&f.values[3]==0&&f.values[4]==0x6464);
 assert(fm_audio_prepare(&a,io)<0);assert(!fm_audio_play(&a)&&f.values[0]==2&&a.playing);
 assert(!fm_audio_restore(&a)&&!a.dirty&&!memcmp(f.values,f.original,sizeof(f.values))&&f.analog_volume==0x1414);
 int writes=f.writes;assert(!fm_audio_restore(&a)&&f.writes==writes);
 reset(&f);f.values[0]=0x100;memset(&a,0,sizeof(a));assert(fm_audio_prepare(&a,io)<0&&!f.writes);
 reset(&f);f.powerdown=1;memset(&a,0,sizeof(a));assert(fm_audio_prepare(&a,io)<0&&!f.writes);
 reset(&f);f.power_read_failed=1;assert(fm_audio_prepare(&a,io)<0&&!f.writes);
 for(int fail=1;fail<=5;fail++){reset(&f);f.fail_get=fail;memset(&a,0,sizeof(a));assert(fm_audio_prepare(&a,io)<0&&!f.writes&&!a.dirty);}
 for(int fail=1;fail<=5;fail++){reset(&f);f.fail_at=fail;memset(&a,0,sizeof(a));assert(fm_audio_prepare(&a,io)<0&&!a.dirty&&!memcmp(f.values,f.original,sizeof(f.values)));}
 reset(&f);f.silent_at=4;memset(&a,0,sizeof(a));assert(fm_audio_prepare(&a,io)<0&&!a.dirty&&!memcmp(f.values,f.original,sizeof(f.values)));
 reset(&f);memset(&a,0,sizeof(a));assert(!fm_audio_prepare(&a,io));f.fail_at=f.writes+1;assert(fm_audio_play(&a)<0&&f.values[0]==31&&!a.playing);assert(!fm_audio_restore(&a));
 reset(&f);memset(&a,0,sizeof(a));assert(!fm_audio_prepare(&a,io));f.always_fail_source=1;assert(fm_audio_restore(&a)<0&&a.dirty&&a.restore_failed&&f.values[0]==31);assert(fm_audio_play(&a)<0);
 f.always_fail_source=0;assert(!fm_audio_restore(&a)&&!a.dirty&&!memcmp(f.values,f.original,sizeof(f.values)));
 reset(&f);memset(&a,0,sizeof(a));assert(!fm_audio_prepare(&a,io));f.values[0]|=0x100;
 assert(fm_audio_restore(&a)<0&&a.dirty&&(f.values[0]&31)==31);
 f.values[0]&=~0x100;assert(!fm_audio_restore(&a)&&!a.dirty);
 return 0;
}
