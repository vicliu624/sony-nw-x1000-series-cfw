#include "qqmusic_preview_session.h"
#include <string.h>
static int same(const struct qq_preview_audio_state *a,const struct qq_preview_audio_state *b){
 return a->mute==b->mute&&a->source==b->source&&a->output==b->output&&a->pcm_mix==b->pcm_mix&&a->adc_mix==b->adc_mix&&a->powerdown==b->powerdown&&a->format==b->format&&a->rate==b->rate&&a->channels==b->channels;
}
static int same_mixer(const struct qq_preview_audio_state *a,const struct qq_preview_audio_state *b){
 return a->mute==b->mute&&a->source==b->source&&a->output==b->output&&a->pcm_mix==b->pcm_mix&&a->adc_mix==b->adc_mix&&a->powerdown==b->powerdown;
}
static int review(struct qq_preview_session *s){s->phase=QQ_PREVIEW_REVIEW;s->failed=1;return -1;}
static int clock_ok(struct qq_preview_session *s,uint64_t now){
 if(now<s->last_ms)return -1;
 s->last_ms=now;return 0;
}
int qq_preview_session_init(struct qq_preview_session *s,const struct qq_preview_session_ops *ops){
 if(!s||!ops||!ops->acquire||!ops->read_state||!ops->configure||!ops->write||!ops->mute||!ops->stop||!ops->restore||!ops->release)return -1;
 memset(s,0,sizeof(*s));s->ops=*ops;s->initialized=1;return 0;
}
int qq_preview_session_begin(struct qq_preview_session *s,uint64_t now){
 if(!s||!s->initialized||(s->phase!=QQ_PREVIEW_IDLE&&s->phase!=QQ_PREVIEW_DONE)||s->generation==UINT64_MAX||now>UINT64_MAX-30000||clock_ok(s,now))return -1;
 s->generation++;s->captured=s->changed=s->failed=0;s->deadline_ms=now+30000;s->phase=QQ_PREVIEW_ACQUIRING;return 0;
}
int qq_preview_session_stop(struct qq_preview_session *s,uint64_t now){
 if(!s||!s->initialized)return -1;
 if(s->phase==QQ_PREVIEW_IDLE||s->phase==QQ_PREVIEW_DONE)return 0;
 if(s->phase==QQ_PREVIEW_REVIEW)return -1;
 if(clock_ok(s,now))s->failed=1;
 if(s->phase>=QQ_PREVIEW_STOPPING)return 1;
 s->phase=QQ_PREVIEW_STOPPING;s->deadline_ms=s->last_ms>UINT64_MAX-10000?UINT64_MAX:s->last_ms+10000;return 1;
}
static int stop_failed(struct qq_preview_session *s){s->failed=1;(void)qq_preview_session_stop(s,s->last_ms);return -1;}
static int configure_step(struct qq_preview_session *s){
 struct qq_preview_audio_state actual;int rc=s->ops.configure(s->ops.context,(unsigned)s->configured.rate,(unsigned)s->configured.channels);
 if(rc==1)return 1;
 if(rc)return stop_failed(s);
 memset(&actual,0,sizeof(actual));if(s->ops.read_state(s->ops.context,&actual)||!same(&actual,&s->configured))return stop_failed(s);
 s->phase=QQ_PREVIEW_READY;return 0;
}
int qq_preview_session_poll(struct qq_preview_session *s,uint64_t now){
 struct qq_preview_stop_receipt receipt;struct qq_preview_audio_state actual;int rc;
 if(!s||!s->initialized)return -1;
 if(s->phase==QQ_PREVIEW_REVIEW)return -1;
 if(clock_ok(s,now)){s->failed=1;(void)qq_preview_session_stop(s,s->last_ms);now=s->last_ms;}
 if(s->phase==QQ_PREVIEW_IDLE||s->phase==QQ_PREVIEW_DONE)return s->failed?-1:0;
 if((s->phase==QQ_PREVIEW_ACQUIRING||s->phase==QQ_PREVIEW_CONFIGURING||s->phase>=QQ_PREVIEW_STOPPING)&&now>=s->deadline_ms){
  if(s->phase==QQ_PREVIEW_ACQUIRING||s->phase==QQ_PREVIEW_CONFIGURING)return stop_failed(s);
  return review(s);
 }
 if(s->phase==QQ_PREVIEW_ACQUIRING){
  rc=s->ops.acquire(s->ops.context,s->generation);if(rc==1)return 1;if(rc)return stop_failed(s);
  memset(&actual,0,sizeof(actual));if(s->ops.read_state(s->ops.context,&actual))return stop_failed(s);
  /* Internal mute is not writable through the public low-five-bit setter. */
  if((actual.mute&0x100)||actual.source<0||actual.source>6||actual.output<0||actual.output>3||(actual.powerdown!=0&&actual.powerdown!=1))return stop_failed(s);
  s->saved=actual;s->captured=1;s->phase=QQ_PREVIEW_LEASED;return 0;
 }
 if(s->phase==QQ_PREVIEW_CONFIGURING)return configure_step(s);
 if(s->phase==QQ_PREVIEW_STOPPING){
  memset(&receipt,0,sizeof(receipt));rc=s->ops.stop(s->ops.context,s->generation,&receipt);
  if(rc==1)return 1;
  if(rc)return review(s);
  if(receipt.generation!=s->generation||receipt.producer_exited!=1||receipt.pcm_reset!=1||receipt.pcm_closed!=1||receipt.had_error>1)return review(s);
  if(receipt.had_error)s->failed=1;
  s->phase=s->captured&&s->changed?QQ_PREVIEW_RESTORING:QQ_PREVIEW_RELEASING;return 1;
 }
 if(s->phase==QQ_PREVIEW_RESTORING){
  rc=s->ops.restore(s->ops.context,&s->saved);if(rc==1)return 1;
  if(rc)return review(s);
  memset(&actual,0,sizeof(actual));if(s->ops.read_state(s->ops.context,&actual)||!same_mixer(&actual,&s->saved))return review(s);
  s->phase=QQ_PREVIEW_RELEASING;return 1;
 }
 if(s->phase==QQ_PREVIEW_RELEASING){
  rc=s->ops.release(s->ops.context,s->generation);if(rc==1)return 1;
  if(rc)return review(s);
  s->phase=QQ_PREVIEW_DONE;return s->failed?-1:0;
 }
 return 0;
}
int qq_preview_session_format(struct qq_preview_session *s,unsigned rate,unsigned channels){
 if(!s||!s->initialized||!s->captured||(rate!=32000&&rate!=44100&&rate!=48000)||!channels||channels>2)return -1;
 if(s->phase==QQ_PREVIEW_CONFIGURING){if(s->configured.rate!=(int32_t)rate||s->configured.channels!=(int32_t)channels)return -1;return configure_step(s);}
 if(s->phase!=QQ_PREVIEW_LEASED)return -1;
 s->changed=1;s->configured=s->saved;
 s->configured.mute=(s->saved.mute&~31)|31;s->configured.source=s->configured.output=s->configured.adc_mix=s->configured.powerdown=0;
 s->configured.pcm_mix=0x6464;s->configured.format=16;s->configured.rate=(int32_t)rate;s->configured.channels=(int32_t)channels;
 s->phase=QQ_PREVIEW_CONFIGURING;s->deadline_ms=s->last_ms>UINT64_MAX-10000?UINT64_MAX:s->last_ms+10000;
 return configure_step(s);
}
int qq_preview_session_write(struct qq_preview_session *s,const unsigned char *pcm,unsigned n){
 struct qq_preview_audio_state actual;int rc;
 if(!s||!s->initialized||!pcm||!n||n>4096||(s->phase!=QQ_PREVIEW_READY&&s->phase!=QQ_PREVIEW_PLAYING))return -1;
 rc=s->ops.write(s->ops.context,pcm,n);
 if(rc<0||(unsigned)rc>n)return stop_failed(s);
 if(rc&&s->phase==QQ_PREVIEW_READY){
  if(s->ops.mute(s->ops.context,9))return stop_failed(s);
  s->configured.mute=(s->saved.mute&~31)|9;
  memset(&actual,0,sizeof(actual));if(s->ops.read_state(s->ops.context,&actual)||!same(&actual,&s->configured))return stop_failed(s);
  s->phase=QQ_PREVIEW_PLAYING;
 }
 return rc;
}
