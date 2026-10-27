#include "../runtime/platform/pcm_output.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
struct fixture{int mix[5],saved[5],power,busy,wrong_rate,eagain,interrupt,write_error,partial,fail_source_once,dsp_open,mix_open,mutating,resets,writes;unsigned size;unsigned char bytes[20000];};
static volatile int stop;
static int op_open(void*c,const char*p,int flags){struct fixture*f=c;if(!strcmp(p,"/dev/sound/mixer")){assert(flags==2&&!f->mix_open);f->mix_open=1;return 10;}assert(!strcmp(p,"/dev/sound/dsp")&&flags==(1|0x800));if(f->busy)return -EBUSY;assert(!f->dsp_open);f->dsp_open=1;return 11;}
static int op_close(void*c,int fd){struct fixture*f=c;if(fd==10){assert(f->mix_open);f->mix_open=0;}else{assert(fd==11&&f->dsp_open);f->dsp_open=0;}return 0;}
static int control(void*c,int fd,uint32_t n,void*arg){struct fixture*f=c;int32_t*v=arg;if(fd==11){assert(f->dsp_open);if(n==HB_PCM_RESET){assert(!arg);f->resets++;return 0;}if(n==HB_PCM_FORMAT){assert(*v==HB_PCM_S16_LE);return 0;}if(n==HB_PCM_CHANNELS){assert(*v==2);return 0;}if(n==HB_PCM_SPEED){assert(*v==22050);if(f->wrong_rate)*v=44100;return 0;}assert(n==HB_PCM_FRAGMENT&&*v==((8<<16)|10));return 0;}assert(fd==10&&f->mix_open);if(n==FM_AUDIO_GET_CODEC_POWERDOWN){*v=f->power;return 0;}uint32_t gets[]={FM_AUDIO_GET_MUTE,FM_AUDIO_GET_SOURCE,FM_AUDIO_GET_OUTPUT,FM_AUDIO_GET_PCM,FM_AUDIO_GET_ADC};uint32_t sets[]={FM_AUDIO_SET_MUTE,FM_AUDIO_SET_SOURCE,FM_AUDIO_SET_OUTPUT,FM_AUDIO_SET_PCM,FM_AUDIO_SET_ADC};for(unsigned i=0;i<5;i++){if(n==gets[i]){*v=f->mix[i];return 0;}if(n==sets[i]){f->mutating++;if(i==1&&f->fail_source_once&&*v==f->saved[1]){f->fail_source_once=0;return 0;}f->mix[i]=i==0?(f->mix[0]&0x100)|(*v&31):*v;return 0;}}assert(0);return -EINVAL;}
static long output(void*c,int fd,const void*p,unsigned n){struct fixture*f=c;assert(fd==11&&f->dsp_open);f->writes++;if(f->interrupt){f->interrupt=0;return -EINTR;}if(f->write_error)return -EIO;if(f->eagain)return -EAGAIN;if(f->partial&&n>(unsigned)f->partial)n=f->partial;assert(f->size+n<=sizeof f->bytes);memcpy(f->bytes+f->size,p,n);f->size+=n;return n;}
static void init(struct fixture*f,struct hb_pcm_output*p){memset(f,0,sizeof(*f));int a[]={0,6,1,0x3232,0x2020};memcpy(f->mix,a,sizeof a);memcpy(f->saved,a,sizeof a);stop=0;hb_pcm_init(p);}
static int start(struct fixture*f,struct hb_pcm_output*p){return hb_pcm_start(p,(struct hb_pcm_ops){f,op_open,op_close,control,output},&stop);}
static void restored(struct fixture*f){assert(!f->mix_open&&!f->dsp_open);assert(!memcmp(f->mix,f->saved,sizeof f->mix));}
int main(void){struct fixture f;struct hb_pcm_output p;unsigned char input[]={0,128,255,64};unsigned char wanted[]={0,0xc0,0,0,0x80,0x3f,0,0xe0};
init(&f,&p);assert(!start(&f,&p));assert(f.mix[0]==31&&!p.route.playing);hb_pcm_volume(&p,50);f.partial=3;f.interrupt=1;assert(!hb_pcm_submit_u8(&p,input,4));assert(f.size==8&&!memcmp(f.bytes,wanted,8)&&f.mix[0]==9);assert(!hb_pcm_close(&p));restored(&f);
init(&f,&p);assert(!start(&f,&p));f.eagain=1;assert(!hb_pcm_submit_u8(&p,input,4)&&p.used==8&&!p.route.playing);f.eagain=0;assert(!hb_pcm_flush(&p)&&p.used==0);assert(!hb_pcm_pause(&p)&&f.mix[0]==31);assert(!hb_pcm_submit_u8(&p,input,4)&&f.mix[0]==9);assert(!hb_pcm_close(&p));restored(&f);
init(&f,&p);assert(!start(&f,&p));f.eagain=1;unsigned char many[2048];memset(many,128,sizeof many);assert(!hb_pcm_submit_u8(&p,many,sizeof many));assert(!hb_pcm_submit_u8(&p,many,sizeof many));assert(p.used==8192);assert(!hb_pcm_submit_u8(&p,many,sizeof many)&&p.dropped==1&&p.used==8192);stop=1;int writes=f.writes;assert(hb_pcm_submit_u8(&p,input,4)<0&&writes==f.writes);assert(!hb_pcm_close(&p));restored(&f);
init(&f,&p);f.power=1;assert(start(&f,&p)<0&&!f.mutating);assert(p.fault_stage==PCM_CODEC_POWER&&p.fault_code==EAGAIN&&p.fault_value==1);restored(&f);
init(&f,&p);f.busy=1;assert(start(&f,&p)<0&&!f.mutating);assert(p.fault_stage==PCM_DSP_OPEN&&p.fault_code==EBUSY);restored(&f);
init(&f,&p);f.wrong_rate=1;assert(start(&f,&p)<0&&!f.mutating);assert(p.fault_stage==PCM_SET_RATE&&p.fault_code==EPROTO&&p.fault_value==44100);restored(&f);
init(&f,&p);f.mix[0]=f.saved[0]=0x100;assert(start(&f,&p)<0&&!f.mutating);restored(&f);
init(&f,&p);assert(!start(&f,&p));f.write_error=1;assert(hb_pcm_submit_u8(&p,input,4)<0&&p.failed&&f.mix[0]==31);assert(p.fault_stage==PCM_WRITE&&p.fault_code==EIO);assert(!hb_pcm_close(&p));restored(&f);
init(&f,&p);assert(!start(&f,&p));f.fail_source_once=1;assert(hb_pcm_close(&p)<0&&p.route.dirty&&f.mix_open&&!f.dsp_open);assert(!hb_pcm_close(&p));restored(&f);
puts("PCM: U8 to S16LE stereo, gain, partial writes, EINTR/EAGAIN, bounded queue, pause/resume, busy/power/rate gates, write failure and FM-route restoration retry passed");return 0;}
