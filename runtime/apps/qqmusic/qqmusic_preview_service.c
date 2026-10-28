#define _XOPEN_SOURCE 700
#include "qqmusic_preview_service.h"
#include "qqmusic_preview_owners.h"
#include <unistd.h>
#include <errno.h>
#include <string.h>
extern ssize_t service_read(int,void *,size_t) __asm__("read");
extern ssize_t service_write(int,const void *,size_t) __asm__("write");
/* 1 full record,0 partial/interrupted,2 would-block,-2 EOF,-1 error.
 * Never read into the following packet. */
static int collect(int fd,unsigned char *data,unsigned *used,unsigned wanted){
 ssize_t n;if(*used==wanted)return 1;
 n=service_read(fd,data+*used,wanted-*used);
 if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))return 2;
 if(n<0&&errno==EINTR)return 0;
 if(!n)return -2;
 if(n<0)return -1;
 *used+=(unsigned)n;return *used==wanted?1:0;
}
static void fail(struct qq_preview_service *s,uint64_t now){s->failed=s->session.failed=1;(void)qq_preview_session_stop(&s->session,now);}
int qq_preview_service_init(struct qq_preview_service *s,const struct qq_preview_device_io *io){
 if(!s||!io)return -1;
 memset(s,0,sizeof(*s));
 if(qq_preview_device_init(&s->device,io)||qq_preview_session_init(&s->session,qq_preview_device_operations(&s->device)))return -1;
 s->command_sequence=s->pcm_sequence=s->status_sequence=1;s->last_status=~0u;s->initialized=1;return 0;
}
int qq_preview_service_producer_exited(void *context,uint64_t generation){
 struct qq_preview_service *s=context;if(!s||!s->initialized||generation!=s->session.generation)return -1;
 return s->bound?qq_preview_producer_exited(&s->producer,generation):1;
}
static int command(struct qq_preview_service *s,const struct qq_preview_server_channels *c,uint64_t now){
 struct qq_preview_record r;uint64_t generation=s->session.generation;int rc;
 rc=collect(c->command,s->command,&s->command_used,32);
 if(rc==-2&&!s->command_used&&(s->session.phase==QQ_PREVIEW_IDLE||s->session.phase==QQ_PREVIEW_DONE))return 0;
 if(rc!=1)return rc;
 if(s->command[5]==QQ_PREVIEW_BEGIN){if(generation==UINT64_MAX)return -1;generation++;}
 if(qq_preview_record_decode(s->command,32,generation,s->command_sequence,&r)||s->command_sequence==UINT32_MAX)return -1;
 s->command_sequence++;s->command_used=0;
 switch(r.type){
 case QQ_PREVIEW_BEGIN:
  if(s->session.phase==QQ_PREVIEW_DONE){
   /* Stop can leave old-generation PCM in the pipe. The producer is already
    * confirmed retired by DONE; discard a bounded amount before a new epoch.
    * Keep this BEGIN record pending until the old pipe is actually empty. */
   ssize_t n=service_read(c->pcm,s->payload,sizeof(s->payload));
   if(n>0||(n<0&&errno==EINTR)){s->command_sequence--;s->command_used=32;return 0;}
   if(n==0||(n<0&&errno!=EAGAIN&&errno!=EWOULDBLOCK))return -1;
  }
  if((s->session.phase!=QQ_PREVIEW_IDLE&&s->session.phase!=QQ_PREVIEW_DONE)||qq_preview_session_begin(&s->session,now))return -1;
  s->bound=s->ended=s->draining=s->failed=0;s->accepted_frames=0;s->max_frames=(uint64_t)r.argument*44100u/1000u;
  s->pcm_used=s->pcm_wanted=s->payload_used=s->payload_sent=0;s->pcm_sequence=1;s->last_status=~0u;
  return qq_preview_producer_init(&s->producer,generation,s->ui_pid,s->ui_birth)?-1:1;
 case QQ_PREVIEW_BIND:
  if(s->bound||s->session.phase!=QQ_PREVIEW_ACQUIRING||qq_preview_producer_bind(&s->producer,generation,r.argument,r.value))return -1;
  s->bound=1;return 1;
 case QQ_PREVIEW_STOP:
  if(qq_preview_session_stop(&s->session,now)<0)return -1;
  return 1;
 default:return -1;
 }
}
static int consume_pcm(struct qq_preview_service *s,const struct qq_preview_server_channels *c){
 struct qq_preview_record r;int rc;
 if(s->pcm_wanted){
  rc=collect(c->pcm,s->payload,&s->payload_used,s->pcm_wanted);if(rc!=1)return rc;
  if(s->session.phase!=QQ_PREVIEW_READY&&s->session.phase!=QQ_PREVIEW_PLAYING)return 0;
  rc=qq_preview_session_write(&s->session,s->payload+s->payload_sent,s->pcm_wanted-s->payload_sent);
  if(rc<0)return -1;
  s->payload_sent+=(unsigned)rc;
  if(s->payload_sent==s->pcm_wanted){s->accepted_frames+=s->pcm_wanted/4u;s->pcm_wanted=s->payload_used=s->payload_sent=0;}
  return 0;
 }
 rc=collect(c->pcm,s->pcm_header,&s->pcm_used,32);if(rc!=1)return rc;
 if(qq_preview_record_decode(s->pcm_header,32,s->session.generation,s->pcm_sequence,&r)||s->pcm_sequence==UINT32_MAX)return -1;
 s->pcm_sequence++;s->pcm_used=0;
 if(r.type==QQ_PREVIEW_FORMAT){
  if(s->session.phase!=QQ_PREVIEW_LEASED)return -1;
  return qq_preview_session_format(&s->session,r.argument,(unsigned)r.value)<0?-1:1;
 }
 if(r.type==QQ_PREVIEW_PCM){
  if((s->session.phase!=QQ_PREVIEW_CONFIGURING&&s->session.phase!=QQ_PREVIEW_READY&&s->session.phase!=QQ_PREVIEW_PLAYING)||s->accepted_frames+r.argument/4u>s->max_frames)return -1;
  s->pcm_wanted=r.argument;return 1;
 }
 if(r.type==QQ_PREVIEW_END){
  if(r.value!=s->accepted_frames||!s->accepted_frames||s->session.phase!=QQ_PREVIEW_PLAYING)return -1;
  s->ended=1;if(r.argument)return -1;s->draining=1;return 1;
 }
 return -1;
}
static int status(struct qq_preview_service *s,const struct qq_preview_server_channels *c,unsigned reaped){
 unsigned value;struct qq_preview_record r;ssize_t n;
 if(reaped||!s->session.generation)return 0;
 value=(unsigned)s->session.phase|(s->bound?0x100u:0)|(s->draining?0x200u:0)|(s->failed||s->session.failed?0x400u:0);
 if(!s->status_pending){
  /* Progress frames change even when phase does not. Coalesce to one record,
   * never retain an unbounded status queue while UI is busy. */
  if(value==s->last_status&&s->accepted_frames==s->last_frames)return 0;
  r.generation=s->session.generation;r.sequence=s->status_sequence;r.type=QQ_PREVIEW_STATUS;r.argument=value;r.value=s->accepted_frames;
  if(qq_preview_record_encode(&r,s->status,32))return -1;
  s->status_pending=1;s->pending_status=value;s->pending_frames=s->accepted_frames;
 }
 n=service_write(c->status,s->status,32);
 if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR))return 0;
 if(n!=32||s->status_sequence==UINT32_MAX)return -1;
 s->status_sequence++;s->status_pending=0;s->last_status=s->pending_status;s->last_frames=s->pending_frames;return 0;
}
int qq_preview_service_pump(struct qq_preview_service *s,const struct qq_preview_server_channels *c,unsigned reaped,unsigned stopped,uint64_t now){
 int rc;unsigned parent;uint64_t birth;
 if(!s||!s->initialized||!c||c->ui_pid<=1)return -1;
 if(!s->ui_pid){
  if(reaped)return 1;
  if(qq_preview_process_identity((unsigned)c->ui_pid,&parent,&birth)!=1||parent!=(unsigned)getpid())return -1;
  s->ui_pid=(unsigned)c->ui_pid;s->ui_birth=birth;
 }else if(s->ui_pid!=(unsigned)c->ui_pid)return -1;
 if(reaped||stopped)(void)qq_preview_session_stop(&s->session,now);
 else if(command(s,c,now)<0)fail(s,now);
 if(s->session.phase==QQ_PREVIEW_ACQUIRING&&!s->bound&&now>=s->session.deadline_ms)fail(s,now);
 if(s->bound&&s->session.phase==QQ_PREVIEW_ACQUIRING)(void)qq_preview_session_poll(&s->session,now);
 else if(s->session.phase>=QQ_PREVIEW_CONFIGURING)(void)qq_preview_session_poll(&s->session,now);
 if(s->bound&&!s->ended&&s->session.phase>=QQ_PREVIEW_LEASED&&s->session.phase<=QQ_PREVIEW_PLAYING){
  unsigned budget;
  /* A single packet step per 20ms supervisor tick cannot feed 176400 B/s.
   * Drain a bounded burst while progress is possible, retaining one packet
   * only. EAGAIN/configuration/backpressure yields promptly for commands. */
  for(budget=0;budget<32;budget++){
   unsigned header=s->pcm_used,used=s->payload_used,sent=s->payload_sent,wanted=s->pcm_wanted;
   uint64_t frames=s->accepted_frames;
   rc=consume_pcm(s,c);
   if(rc<0||(rc==2&&qq_preview_service_producer_exited(s,s->session.generation)!=0)){fail(s,now);break;}
   if(rc==2||s->ended||s->session.phase>=QQ_PREVIEW_STOPPING)break;
   if(!rc&&header==s->pcm_used&&used==s->payload_used&&sent==s->payload_sent&&wanted==s->pcm_wanted&&frames==s->accepted_frames)break;
  }
 }
 if(s->draining&&s->session.phase==QQ_PREVIEW_PLAYING){
  rc=qq_preview_device_drain(&s->device,s->session.generation,now);
  if(rc<0)fail(s,now);else if(!rc){s->draining=0;(void)qq_preview_session_stop(&s->session,now);}
 }
 if(status(s,c,reaped)<0)fail(s,now);
 if(s->failed&&!s->session.generation&&!reaped&&!stopped)return -1;
 if(s->session.phase==QQ_PREVIEW_REVIEW)return -1;
 return s->session.phase==QQ_PREVIEW_IDLE||s->session.phase==QQ_PREVIEW_DONE?1:0;
}
