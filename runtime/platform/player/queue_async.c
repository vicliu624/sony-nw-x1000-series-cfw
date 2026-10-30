#include "queue_async.h"
#include <string.h>
extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *,const void *),pthread_mutex_trylock(void *),pthread_mutex_lock(void *),pthread_mutex_unlock(void *),pthread_mutex_destroy(void *);
extern int pthread_cond_init(void *,const void *),pthread_cond_wait(void *,void *),pthread_cond_signal(void *),pthread_cond_destroy(void *);
extern int pthread_attr_init(void *),pthread_attr_setdetachstate(void *,int),pthread_attr_destroy(void *);
extern int pthread_create(unsigned long *,const void *,void *(*)(void *),void *);
#define BOUND 0x58575141u
#define QUEUED 1u
#define RUNNING 2u
#define DONE 3u
static void revoke(struct xw_queue_async *s){if(!++s->epoch)++s->epoch;s->cache_valid=0;s->status=XW_PLAYER_UNAVAILABLE;s->next_attempt=0;}
static int same(const struct xw_queue_plan *a,const struct xw_queue_plan *b){
 if(a->kind!=b->kind)return 0;
 if(a->kind==1){
  /* Current playback position does not change the unshuffled group query. */
  return a->generation==b->generation&&a->revision==b->revision&&a->group_limit==b->group_limit&&a->source.order.offset==b->source.order.offset&&a->grouped.total==b->grouped.total&&a->grouped.shuffled==b->grouped.shuffled&&xw_query_snapshot_equal(&a->grouped.groups,&b->grouped.groups)&&xw_query_snapshot_equal(&a->grouped.track_filter,&b->grouped.track_filter);
 }
 return !memcmp(a,b,sizeof *a);
}
static void cancel_queued(struct xw_queue_async *s){if(s->phase==QUEUED){xw_stock_media_close(&s->media);memset(&s->media,0,sizeof s->media);s->phase=0;}}
static void *reader(void *argument){
 struct xw_queue_async *s=argument;pthread_mutex_lock(&s->mutex);
 for(;;){
  while(!s->closing&&s->phase!=QUEUED){if(pthread_cond_wait(&s->condition,&s->mutex)){s->closing=1;break;}}
  if(s->closing){s->exited=1;pthread_mutex_unlock(&s->mutex);return 0;}
  uint64_t epoch=s->job_epoch;s->phase=RUNNING;pthread_mutex_unlock(&s->mutex);
  int rc;unsigned progress=0;
  if(s->job.kind==1){
   rc=0;if(s->group_epoch!=epoch){
    xw_group_reader_reset(&s->group_reader);rc=xw_group_reader_begin(&s->group_reader,&s->job.grouped,s->job.generation,s->job.source.order.offset,s->job.group_limit);s->group_epoch=epoch;
   }
   unsigned phase=s->group_reader.phase;uint32_t position=s->group_reader.position,index=s->group_reader.group_index;
   if(!rc)rc=xw_group_native_step(&s->media,&s->group_reader,&s->group_workspace,&s->result);
   else{int adopt=xw_stock_media_adopt(&s->media);int closed=adopt?adopt:xw_stock_media_close(&s->media);if(closed)rc=closed;}
   progress=phase!=s->group_reader.phase||position!=s->group_reader.position||index!=s->group_reader.group_index;
   if(rc!=XW_PLAYER_BUSY)s->group_epoch=0;
  }else{
   s->group_epoch=0;rc=xw_queue_page_read(&s->media,&s->job,&s->workspace,&s->result);
   int close_rc=xw_stock_media_close(&s->media);if(close_rc)rc=close_rc;
  }
  pthread_mutex_lock(&s->mutex);memset(&s->media,0,sizeof s->media);
  s->result_code=rc;s->result_progress=progress;s->result_epoch=epoch;s->phase=DONE;
 }
}
static int start(struct xw_queue_async *s){
 if(s->started)return 0;union xw_pthread_storage attr;
 if(pthread_attr_init(&attr))return XW_PLAYER_UNAVAILABLE;
 int rc=pthread_attr_setdetachstate(&attr,1);if(!rc)rc=pthread_create(&s->thread,&attr,reader,s);
 pthread_attr_destroy(&attr);if(rc)return XW_PLAYER_UNAVAILABLE;s->started=1;return 0;
}
int xw_queue_async_init(struct xw_queue_async *s){
 if(!s)return XW_PLAYER_INVALID;if(s->initialized)return XW_PLAYER_BUSY;memset(s,0,sizeof *s);
 if(pthread_mutex_init(&s->mutex,0))return XW_PLAYER_UNAVAILABLE;
 if(pthread_cond_init(&s->condition,0)){pthread_mutex_destroy(&s->mutex);return XW_PLAYER_UNAVAILABLE;}
 s->owner=pthread_self();s->epoch=1;s->status=XW_PLAYER_UNAVAILABLE;s->initialized=BOUND;return 0;
}
int xw_queue_async_observe(struct xw_queue_async *s,const struct xw_queue_plan *p,uint64_t now,struct xw_queue_result *out){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;if(!out||(p&&p->kind>1))return XW_PLAYER_INVALID;if(s->owner!=pthread_self())return XW_PLAYER_BUSY;
 if((p!=0)!=s->desired_valid||(p&&!same(p,&s->desired))||now<s->last){revoke(s);s->desired_valid=p!=0;if(p)s->desired=*p;}
 s->last=now;
 if(pthread_mutex_trylock(&s->mutex)){if(p&&s->cache_valid){*out=s->cache;return 0;}return XW_PLAYER_BUSY;}
 if(s->closing){pthread_mutex_unlock(&s->mutex);return XW_PLAYER_CLOSED;}
 if(s->phase==QUEUED&&s->job_epoch!=s->epoch)cancel_queued(s);
 if(s->phase==DONE){
  if(s->result_epoch==s->epoch){s->status=s->result_code;s->cache_valid=!s->result_code;if(s->cache_valid){s->cache=s->result;s->next_attempt=now+2000u;}else if(s->desired.kind==1&&s->result_code==XW_PLAYER_BUSY)s->next_attempt=now+(s->result_progress?0u:100u);}
  s->phase=0;
 }
 if(p&&s->cache_valid&&now>=s->next_attempt){s->cache_valid=0;s->status=XW_PLAYER_UNAVAILABLE;}
 if(p&&!s->phase&&!s->cache_valid&&now>=s->next_attempt){
  struct xw_stock_media media={0};int rc=xw_stock_media_open(&media);
  if(!rc){rc=start(s);if(rc)xw_stock_media_close(&media);}
  s->next_attempt=now+1000u;if(rc)s->status=rc;
  else{s->media=media;s->job=*p;s->job_epoch=s->epoch;s->phase=QUEUED;s->status=XW_PLAYER_BUSY;pthread_cond_signal(&s->condition);}
 }
 pthread_mutex_unlock(&s->mutex);if(p&&s->cache_valid){*out=s->cache;return 0;}return p?s->status:XW_PLAYER_UNAVAILABLE;
}
int xw_queue_async_stop(struct xw_queue_async *s){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;if(s->owner!=pthread_self()||pthread_mutex_trylock(&s->mutex))return XW_PLAYER_BUSY;
 s->closing=1;revoke(s);cancel_queued(s);pthread_cond_signal(&s->condition);pthread_mutex_unlock(&s->mutex);return s->started?XW_PLAYER_ACCEPTED:0;
}
int xw_queue_async_drained(struct xw_queue_async *s){
 if(!s||s->initialized!=BOUND||s->owner!=pthread_self()||pthread_mutex_trylock(&s->mutex))return 0;
 int done=s->closing&&(!s->started||s->exited);pthread_mutex_unlock(&s->mutex);return done;
}
int xw_queue_async_destroy(struct xw_queue_async *s){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;if(!xw_queue_async_drained(s))return XW_PLAYER_BUSY;
 pthread_cond_destroy(&s->condition);pthread_mutex_destroy(&s->mutex);memset(s,0,sizeof *s);return 0;
}
