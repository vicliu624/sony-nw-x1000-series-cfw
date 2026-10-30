#include "metadata_async.h"
#include <string.h>
/* Original functions initialize/interpret their own opaque pthread data;
 * modern NPTL structure layouts/static initializers are not assumed here. */
extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *,const void *);
extern int pthread_mutex_trylock(void *);
extern int pthread_mutex_lock(void *);
extern int pthread_mutex_unlock(void *);
extern int pthread_mutex_destroy(void *);
extern int pthread_cond_init(void *,const void *);
extern int pthread_cond_wait(void *,void *);
extern int pthread_cond_signal(void *);
extern int pthread_cond_destroy(void *);
extern int pthread_attr_init(void *);
extern int pthread_attr_setdetachstate(void *,int);
extern int pthread_attr_destroy(void *);
extern int pthread_create(unsigned long *,const void *,void *(*)(void *),void *);
#define ASYNC_BOUND 0x58574d41u
#define QUEUED 1u
#define RUNNING 2u
#define DONE 3u
static void epoch(struct xw_metadata_async *s){if(!++s->generation)++s->generation;s->cache_valid=0;s->next_attempt=0;s->status=XW_PLAYER_UNAVAILABLE;}
static void *reader(void *context){
 struct xw_metadata_async *s=context;pthread_mutex_lock(&s->mutex);
 for(;;){
  while(!s->closing&&s->phase!=QUEUED){if(pthread_cond_wait(&s->condition,&s->mutex)){s->closing=1;s->exited=1;pthread_mutex_unlock(&s->mutex);return 0;}}
  if(s->closing){s->exited=1;pthread_mutex_unlock(&s->mutex);return 0;}
  struct xw_stock_media media=s->job_media;struct xw_media_id id=s->job_id;uint32_t generation=s->job_generation;
  s->phase=RUNNING;pthread_mutex_unlock(&s->mutex);
  struct xw_media_item result;int rc=s->children?xw_stock_media_children(&media,&s->children->job,&s->children->result):s->read_item?s->read_item(&media,&id,&result):xw_stock_media_fetch(&media,&id,&result);int close_rc=xw_stock_media_close(&media);if(!rc&&close_rc)rc=close_rc;
  pthread_mutex_lock(&s->mutex);memset(&s->job_media,0,sizeof s->job_media);
  s->result_code=rc;if(!rc&&!s->children)s->result=result;s->result_generation=generation;s->phase=DONE;
 }
}
int xw_metadata_async_init(struct xw_metadata_async *s){
 if(!s)return XW_PLAYER_INVALID;if(s->initialized)return XW_PLAYER_BUSY;memset(s,0,sizeof *s);
 if(pthread_mutex_init(&s->mutex,0))return XW_PLAYER_UNAVAILABLE;
 if(pthread_cond_init(&s->condition,0)){pthread_mutex_destroy(&s->mutex);return XW_PLAYER_UNAVAILABLE;}
 s->owner=pthread_self();s->initialized=ASYNC_BOUND;s->generation=1;s->status=XW_PLAYER_UNAVAILABLE;return 0;
}
static int start_reader(struct xw_metadata_async *s){
 if(s->started)return 0;union xw_pthread_storage attributes;
 if(pthread_attr_init(&attributes))return XW_PLAYER_UNAVAILABLE;
 int rc=pthread_attr_setdetachstate(&attributes,1);if(!rc)rc=pthread_create(&s->thread,&attributes,reader,s);
 pthread_attr_destroy(&attributes);if(rc)return XW_PLAYER_UNAVAILABLE;s->started=1;return 0;
}
static void cancel_queued(struct xw_metadata_async *s){if(s->phase==QUEUED){xw_stock_media_close(&s->job_media);memset(&s->job_media,0,sizeof s->job_media);s->phase=0;}}
int xw_metadata_async_observe(struct xw_metadata_async *s,const struct xw_media_id *id,uint64_t revision,unsigned long long now,struct xw_media_item *out){
 if(!s||s->initialized!=ASYNC_BOUND)return XW_PLAYER_CLOSED;if(!out||s->children)return XW_PLAYER_INVALID;if(s->owner!=pthread_self())return XW_PLAYER_BUSY;
 struct xw_media_id empty={{0}};const struct xw_media_id *desired=id?id:&empty;
 if(memcmp(s->desired.value,desired->value,sizeof desired->value)||s->revision!=revision||now<s->last){epoch(s);s->desired=*desired;s->revision=revision;}
 s->last=now;
 if(pthread_mutex_trylock(&s->mutex)){if(s->cache_valid&&id){*out=s->cache;return 0;}return XW_PLAYER_BUSY;}
 if(s->closing){pthread_mutex_unlock(&s->mutex);return XW_PLAYER_CLOSED;}
 if(s->phase==QUEUED&&s->job_generation!=s->generation)cancel_queued(s);
 if(s->phase==DONE){
  if(s->result_generation==s->generation){
   s->status=s->result_code;
   if(!s->result_code&&!memcmp(s->result.id.value,s->desired.value,sizeof s->desired.value)){s->cache=s->result;s->cache_valid=1;}else{s->cache_valid=0;if(!s->result_code)s->status=XW_PLAYER_PROTOCOL;}
  }
  s->phase=0;
 }
 if(id&&s->phase==0&&now>=s->next_attempt){
  struct xw_stock_media media={0};int rc=xw_stock_media_open(&media);
  if(!rc){rc=start_reader(s);if(rc)xw_stock_media_close(&media);}
  s->next_attempt=now+(rc?1000u:2000u);if(s->read_item&&!s->cache_valid)s->status=rc?rc:XW_PLAYER_BUSY;
  if(!rc){s->job_media=media;s->job_id=*id;s->job_generation=s->generation;s->job_revision=revision;s->phase=QUEUED;pthread_cond_signal(&s->condition);}
 }
 pthread_mutex_unlock(&s->mutex);if(s->cache_valid&&id){*out=s->cache;return 0;}return id&&s->read_item?s->status:XW_PLAYER_UNAVAILABLE;
}
int xw_metadata_async_stop(struct xw_metadata_async *s){
 if(!s||s->initialized!=ASYNC_BOUND)return XW_PLAYER_CLOSED;if(s->owner!=pthread_self())return XW_PLAYER_BUSY;if(pthread_mutex_trylock(&s->mutex))return XW_PLAYER_BUSY;
 s->closing=1;epoch(s);cancel_queued(s);pthread_cond_signal(&s->condition);pthread_mutex_unlock(&s->mutex);return s->started?XW_PLAYER_ACCEPTED:0;
}
int xw_metadata_async_drained(struct xw_metadata_async *s){
 if(!s||s->initialized!=ASYNC_BOUND)return 0;if(pthread_mutex_trylock(&s->mutex))return 0;int result=s->closing&&(!s->started||s->exited);pthread_mutex_unlock(&s->mutex);return result;
}
int xw_metadata_async_destroy(struct xw_metadata_async *s){
 if(!s||s->initialized!=ASYNC_BOUND)return XW_PLAYER_CLOSED;if(s->owner!=pthread_self()||!xw_metadata_async_drained(s))return XW_PLAYER_BUSY;
 cancel_queued(s);pthread_cond_destroy(&s->condition);pthread_mutex_destroy(&s->mutex);memset(s,0,sizeof *s);return 0;
}

int xw_children_async_init(struct xw_children_async *c){
 if(!c)return XW_PLAYER_INVALID;if(c->worker.initialized)return XW_PLAYER_BUSY;
 memset(c,0,sizeof *c);int rc=xw_metadata_async_init(&c->worker);if(!rc){c->worker.children=c;c->status=XW_PLAYER_UNAVAILABLE;}return rc;
}
static int same_query(const struct xw_stock_children_query *a,const struct xw_stock_children_query *b){
 return a->kind==b->kind&&a->offset==b->offset&&a->limit==b->limit&&!memcmp(a->parent.value,b->parent.value,sizeof a->parent.value);
}
int xw_children_async_observe(struct xw_children_async *c,const struct xw_stock_children_query *q,uint64_t revision,unsigned long long now,struct xw_stock_children_page *out){
 if(!c||c->worker.initialized!=ASYNC_BOUND||c->worker.children!=c)return XW_PLAYER_CLOSED;
 struct xw_metadata_async *s=&c->worker;if(!out)return XW_PLAYER_INVALID;if(s->owner!=pthread_self())return XW_PLAYER_BUSY;
 if(q&&(q->kind>XW_STOCK_FORMAT3_CHILDREN||!q->limit||q->limit>XW_MEDIA_PAGE_MAX||q->offset>0x7fffffffu-q->limit))return XW_PLAYER_INVALID;
 if((q!=0)!=c->desired_valid||(q&&!same_query(q,&c->desired))||revision!=s->revision||now<s->last){
  epoch(s);c->status=XW_PLAYER_UNAVAILABLE;c->desired_valid=q!=0;if(q)c->desired=*q;s->revision=revision;
 }
 s->last=now;
 if(pthread_mutex_trylock(&s->mutex)){if(q&&s->cache_valid){*out=c->cache;return 0;}return XW_PLAYER_BUSY;}
 if(s->closing){pthread_mutex_unlock(&s->mutex);return XW_PLAYER_CLOSED;}
 if(s->phase==QUEUED&&s->job_generation!=s->generation)cancel_queued(s);
 if(s->phase==DONE){
  if(s->result_generation==s->generation){c->status=s->result_code;s->cache_valid=!s->result_code;if(s->cache_valid){c->cache=c->result;s->next_attempt=now+2000u;}}
  s->phase=0;
 }
 if(q&&!revision&&s->cache_valid&&now>=s->next_attempt){s->cache_valid=0;c->status=XW_PLAYER_UNAVAILABLE;}
 if(q&&s->phase==0&&!s->cache_valid&&now>=s->next_attempt){
  struct xw_stock_media media={0};int rc=xw_stock_media_open(&media);
  if(!rc){rc=start_reader(s);if(rc)xw_stock_media_close(&media);}
  s->next_attempt=now+1000u;if(rc)c->status=rc;
  if(!rc){c->status=XW_PLAYER_BUSY;s->job_media=media;c->job=*q;s->job_generation=s->generation;s->phase=QUEUED;pthread_cond_signal(&s->condition);}
 }
 pthread_mutex_unlock(&s->mutex);if(q&&s->cache_valid){*out=c->cache;return 0;}return q?c->status:XW_PLAYER_UNAVAILABLE;
}
