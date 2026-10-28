#include "../../runtime/apps/qqmusic/qqmusic_preview_session.h"
#include <assert.h>
#include <string.h>
struct model {
 struct qq_preview_audio_state original,state;
 unsigned owned,stopped,configured,restored,released,writes,mutes,accepted;
 int acquire_pending,stop_pending,restore_pending,release_pending;
 int configure_pending,configure_fail,bad_format,stop_fail,stale,missing_exit,bad_restore,mute_fail;
 unsigned fragment,backpressure;
};
static struct model m;static struct qq_preview_session s;static uint64_t now;
static int acquire(void *p,uint64_t generation){struct model *v=p;assert(generation);if(v->acquire_pending){v->acquire_pending--;return 1;}v->owned=1;return 0;}
static int read_state(void *p,struct qq_preview_audio_state *out){*out=((struct model *)p)->state;return 0;}
static int configure(void *p,unsigned rate,unsigned channels){
 struct model *v=p;assert(v->owned&&!v->stopped);v->configured=1;
 if(v->configure_pending){v->configure_pending--;return 1;}
 v->state.mute=31;v->state.source=v->state.output=v->state.adc_mix=v->state.powerdown=0;v->state.pcm_mix=0x6464;v->state.format=16;v->state.rate=(int32_t)rate;v->state.channels=(int32_t)channels;
 if(v->bad_format)v->state.rate=22050;
 return v->configure_fail?-1:0;
}
static int write_pcm(void *p,const unsigned char *data,unsigned n){
 struct model *v=p;unsigned take=n,i;assert(v->owned&&v->configured&&!v->stopped);v->writes++;
 if(v->backpressure){v->backpressure--;return 0;}
 if(v->fragment&&take>v->fragment)take=v->fragment;
#ifndef QQ_SESSION_REAL_PCM
 for(i=0;i<take;i++)assert(data[i]==(unsigned char)(v->accepted+i));
#else
 (void)data;(void)i;
#endif
 v->accepted+=take;return (int)take;
}
static int mute(void *p,int32_t value){struct model *v=p;assert(v->accepted&&value==9);v->mutes++;if(v->mute_fail)return -1;v->state.mute=value;return 0;}
static int stop_pcm(void *p,uint64_t generation,struct qq_preview_stop_receipt *out){
 struct model *v=p;if(v->stop_pending){v->stop_pending--;return 1;}if(v->stop_fail)return -1;
 out->generation=generation-(v->stale?1:0);out->producer_exited=v->missing_exit?0:1;out->pcm_reset=out->pcm_closed=1;
 v->stopped=1;if(v->configured)v->state.mute=31;v->state.rate=v->state.channels=v->state.format=0;return 0;
}
static int restore(void *p,const struct qq_preview_audio_state *old){
 struct model *v=p;assert(v->stopped&&v->owned);if(v->restore_pending){v->restore_pending--;return 1;}
 v->restored++;if(!v->bad_restore)v->state=*old;return 0;
}
static int release(void *p,uint64_t generation){struct model *v=p;assert(generation&&v->stopped&&v->owned);if(v->configured)assert(v->restored);if(v->release_pending){v->release_pending--;return 1;}v->owned=0;v->released++;return 0;}
static void setup(void){
 struct qq_preview_session_ops ops={&m,acquire,read_state,configure,write_pcm,mute,stop_pcm,restore,release};
 memset(&m,0,sizeof(m));m.original.source=2;m.original.output=1;m.original.pcm_mix=0x3232;m.original.adc_mix=0x2020;m.state=m.original;now=100;
 assert(!qq_preview_session_init(&s,&ops));assert(!qq_preview_session_begin(&s,now));
}
static int poll_session(void){now+=20;return qq_preview_session_poll(&s,now);}
static void ready(void){assert(!poll_session()&&s.phase==QQ_PREVIEW_LEASED);assert(!qq_preview_session_format(&s,44100,2)&&s.phase==QQ_PREVIEW_READY);}
static void finish(void){unsigned i;for(i=0;i<8&&s.phase!=QQ_PREVIEW_DONE&&s.phase!=QQ_PREVIEW_REVIEW;i++)(void)poll_session();}
int main(void){
 unsigned i,used;unsigned char pcm[32];struct qq_preview_session empty={0};
 assert(qq_preview_session_begin(&empty,1)<0&&qq_preview_session_poll(&empty,1)<0);
 for(i=0;i<sizeof(pcm);i++)pcm[i]=(unsigned char)i;
 setup();assert(!poll_session());m.configure_pending=2;assert(qq_preview_session_format(&s,44100,2)==1&&s.phase==QQ_PREVIEW_CONFIGURING);assert(qq_preview_session_write(&s,pcm,sizeof(pcm))<0&&!m.writes);assert(poll_session()==1&&s.phase==QQ_PREVIEW_CONFIGURING);assert(!poll_session()&&s.phase==QQ_PREVIEW_READY);assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_DONE);
 setup();m.acquire_pending=1;assert(poll_session()==1&&s.phase==QQ_PREVIEW_ACQUIRING);assert(qq_preview_session_format(&s,44100,2)<0&&!m.configured&&!m.writes);ready();
 m.fragment=1;m.backpressure=1;assert(!qq_preview_session_write(&s,pcm,sizeof(pcm))&&!m.mutes&&s.phase==QQ_PREVIEW_READY);
 for(used=0;used<sizeof(pcm);){int n=qq_preview_session_write(&s,pcm+used,(unsigned)sizeof(pcm)-used);assert(n==1);used+=(unsigned)n;}
 assert(m.accepted==sizeof(pcm)&&m.mutes==1&&s.phase==QQ_PREVIEW_PLAYING);
 m.stop_pending=m.restore_pending=m.release_pending=1;assert(qq_preview_session_stop(&s,now)==1);assert(qq_preview_session_write(&s,pcm,sizeof(pcm))<0);assert(poll_session()==1&&!m.restored&&!m.released);assert(qq_preview_session_begin(&s,now)<0);finish();assert(s.phase==QQ_PREVIEW_DONE&&!s.failed&&!m.owned&&m.released==1);
 assert(!qq_preview_session_begin(&s,now)&&s.generation==2);
 setup();ready();m.stale=1;assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_REVIEW&&m.owned&&!m.restored&&!m.released&&qq_preview_session_begin(&s,now)<0);
 setup();ready();m.missing_exit=1;assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_REVIEW&&!m.restored&&!m.released);
 setup();ready();m.stop_fail=1;assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_REVIEW&&m.owned&&!m.restored&&!m.released);
 setup();ready();m.bad_restore=1;assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_REVIEW&&m.owned&&!m.released&&m.state.mute==31);
 setup();assert(!poll_session());m.configure_fail=1;assert(qq_preview_session_format(&s,44100,2)<0);finish();assert(s.phase==QQ_PREVIEW_DONE&&s.failed&&m.restored&&!m.owned&&poll_session()<0);
 setup();assert(!poll_session());m.bad_format=1;assert(qq_preview_session_format(&s,48000,2)<0);finish();assert(s.phase==QQ_PREVIEW_DONE&&s.failed&&m.restored);
 setup();ready();m.mute_fail=1;assert(qq_preview_session_write(&s,pcm,sizeof(pcm))<0);finish();assert(s.phase==QQ_PREVIEW_DONE&&s.failed&&m.restored&&!m.owned);
 setup();ready();assert(qq_preview_session_poll(&s,now-1)==1);finish();assert(s.phase==QQ_PREVIEW_DONE&&s.failed&&m.restored&&!m.owned);
 setup();m.state.mute|=0x100;assert(poll_session()<0&&!m.configured&&!m.writes);finish();assert(s.phase==QQ_PREVIEW_DONE&&s.failed&&!m.owned);
 setup();ready();m.stop_pending=1000;assert(qq_preview_session_stop(&s,now)==1);now+=10001;assert(qq_preview_session_poll(&s,now)<0&&s.phase==QQ_PREVIEW_REVIEW&&m.owned&&!m.released);
 return 0;
}
