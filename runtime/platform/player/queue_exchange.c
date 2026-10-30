#include "queue_exchange.h"
#include <string.h>
extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *,const void *),pthread_mutex_trylock(void *),pthread_mutex_unlock(void *),pthread_mutex_destroy(void *);
#define BOUND 0x58575145u
static int enter(struct xw_queue_exchange *s){if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;return pthread_mutex_trylock(&s->mutex)?XW_PLAYER_BUSY:0;}
int xw_queue_exchange_init(struct xw_queue_exchange *s){
 if(!s)return XW_PLAYER_INVALID;if(s->initialized)return XW_PLAYER_BUSY;memset(s,0,sizeof *s);
 if(pthread_mutex_init(&s->mutex,0))return XW_PLAYER_UNAVAILABLE;s->gui_owner=pthread_self();s->initialized=BOUND;return 0;
}
int xw_queue_exchange_request(struct xw_queue_exchange *s,uint32_t offset,uint32_t limit){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;if(s->gui_owner!=pthread_self())return XW_PLAYER_BUSY;
 if(limit>XW_MEDIA_PAGE_MAX||offset>UINT32_MAX-limit)return XW_PLAYER_INVALID;
 int rc=enter(s);if(rc)return rc;
 if((limit!=0)!=s->active||(limit&&(offset!=s->request.offset||limit!=s->request.limit))){
  if(s->generation==UINT32_MAX){pthread_mutex_unlock(&s->mutex);return XW_PLAYER_UNAVAILABLE;}
  s->generation++;s->active=limit!=0;s->ready=0;s->request.generation=s->generation;s->request.offset=offset;s->request.limit=limit;
 }
 pthread_mutex_unlock(&s->mutex);return 0;
}
int xw_queue_exchange_take(struct xw_queue_exchange *s,struct xw_queue_request *out){
 if(!out)return XW_PLAYER_INVALID;int rc=enter(s);if(rc)return rc;
 if(!s->active)rc=XW_PLAYER_UNAVAILABLE;else *out=s->request;
 pthread_mutex_unlock(&s->mutex);return rc;
}
int xw_queue_exchange_publish(struct xw_queue_exchange *s,const struct xw_queue_request *request,int status,const struct xw_queue_plan *plan){
 if(!request||status>0||(!status&&(!plan||plan->generation!=request->generation||plan->source.order.offset!=request->offset||plan->source.order.count>request->limit)))return XW_PLAYER_INVALID;
 int rc=enter(s);if(rc)return rc;
 if(!s->active||request->generation!=s->request.generation||request->offset!=s->request.offset||request->limit!=s->request.limit)rc=XW_PLAYER_STALE;
 else{s->status=status;if(!status)s->plan=*plan;s->ready=1;}
 pthread_mutex_unlock(&s->mutex);return rc;
}
int xw_queue_exchange_read(struct xw_queue_exchange *s,struct xw_queue_plan *out){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;if(!out)return XW_PLAYER_INVALID;if(s->gui_owner!=pthread_self())return XW_PLAYER_BUSY;
 int rc=enter(s);if(rc)return rc;
 if(!s->active)rc=XW_PLAYER_UNAVAILABLE;else if(!s->ready)rc=XW_PLAYER_BUSY;else{rc=s->status;if(!rc)*out=s->plan;}
 pthread_mutex_unlock(&s->mutex);return rc;
}
int xw_queue_exchange_destroy(struct xw_queue_exchange *s){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;if(s->gui_owner!=pthread_self())return XW_PLAYER_BUSY;
 if(pthread_mutex_destroy(&s->mutex))return XW_PLAYER_BUSY;memset(s,0,sizeof *s);return 0;
}
