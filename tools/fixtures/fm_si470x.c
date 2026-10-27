#include <assert.h>
#include <string.h>
#include "../../runtime/apps/fm-radio/fm_si470x.h"
struct fake {uint32_t frequency,fail;int wrong_name,wrong_unit,short_band,mismatch,bad_signal,valid,sets,not_done,wrong_channel,config,read_error,waits,cancel,read_error_index,config_writes,drop_write,fail_applied;};
static int control(void *context,uint32_t request,void *arg){
 struct fake *f=context;if(f->fail==request)return -1;
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
static int wait_ms(void *p,unsigned ms){struct fake *f=p;assert(ms==10);f->waits++;return f->cancel?-1:0;}
int main(void){
 struct fake f={0};struct fm_si470x s;struct fm_band band={76000,90000,100};
 struct fm_tuner_transport io={&f,control,wait_ms};
 assert(fm_si470x_probe(&s,io,band)==0);struct fm_backend b=fm_si470x_backend(&s);
 assert(b.tune(b.context,82500)==0&&f.frequency==1320000&&f.sets==1);
 assert(b.tune(b.context,108000)<0&&f.sets==1);
 f.not_done=1;assert(b.tune(b.context,82500)<0&&f.waits==5);f.not_done=0;
 f.wrong_channel=1;assert(b.tune(b.context,82500)<0);f.wrong_channel=0;
 f.read_error=1;assert(b.tune(b.context,82500)<0);f.read_error=0;
 f.read_error_index=10;assert(b.tune(b.context,82500)<0);f.read_error_index=11;assert(b.tune(b.context,82500)<0);f.read_error_index=0;
 f.cancel=1;f.not_done=1;assert(b.tune(b.context,82500)<0);f.cancel=f.not_done=0;
 f.config=0x10;assert(b.tune(b.context,82500)<0);f.config=0;
 assert(b.tune(b.context,82500)==0);
 int quality=77;f.read_error_index=10;assert(b.sample(b.context,&quality)<0);f.read_error_index=0;
 f.wrong_channel=1;assert(b.sample(b.context,&quality)<0);f.wrong_channel=0;
 assert(b.sample(b.context,&quality)==0&&quality==0);
 f.valid=1;assert(b.sample(b.context,&quality)==1&&quality==255);
 f.bad_signal=1;assert(b.sample(b.context,&quality)<0);f.bad_signal=0;
 f.mismatch=1;assert(b.tune(b.context,82500)<0);f.mismatch=0;
 f.fail=FM_VIDIOCSFREQ;assert(b.tune(b.context,82500)<0);
 f.fail=FM_VIDIOCGFREQ;assert(b.tune(b.context,82500)<0);
 f.fail=FM_VIDIOCGTUNER;assert(b.sample(b.context,&quality)<0&&fm_si470x_probe(&s,io,band)<0);
 assert(b.tune(b.context,82500)<0);f.fail=0;
 f.wrong_name=1;assert(fm_si470x_probe(&s,io,band)<0);f.wrong_name=0;
 f.wrong_unit=1;assert(fm_si470x_probe(&s,io,band)<0);f.wrong_unit=0;
 f.short_band=1;assert(fm_si470x_probe(&s,io,(struct fm_band){76000,108000,100})<0);
 f.config=0x40;assert(fm_si470x_probe(&s,io,band)<0);f.config=0;
 assert(fm_si470x_probe(&s,io,band)==0);
 assert(!fm_si470x_quiesce(&s));
 struct fm_radio r;assert(fm_init(&r,band,fm_si470x_backend(&s))==0&&fm_tune(&r,82500)==0);
 struct fm_band wide={76000,108000,100};memset(&f,0,sizeof(f));f.config=0x1ca0;
 assert(!fm_si470x_probe(&s,io,wide)&&f.config==0x1c60&&s.config_dirty);
 b=fm_si470x_backend(&s);assert(!b.tune(b.context,107900)&&!b.tune(b.context,108000));assert(b.tune(b.context,108100)<0);
 assert(!fm_si470x_quiesce(&s)&&!fm_si470x_restore_band(&s)&&f.config==0x1ca0&&!s.config_dirty);
 f.config=0x1c00;assert(!fm_si470x_probe(&s,io,wide)&&f.config==0x1c50);assert(!fm_si470x_restore_band(&s)&&f.config==0x1c00);
 f.config=0x1ca0;f.drop_write=1;assert(fm_si470x_probe(&s,io,wide)<0&&f.config==0x1ca0&&!s.config_dirty);f.drop_write=0;
 f.fail_applied=1;assert(fm_si470x_probe(&s,io,wide)<0&&f.config==0x1ca0&&!s.config_dirty);
 assert(!fm_si470x_probe(&s,io,wide));f.fail=FM_VIDIOC_PUTREG;assert(fm_si470x_restore_band(&s)<0&&s.config_dirty);f.fail=0;assert(!fm_si470x_restore_band(&s));
 return 0;
}
