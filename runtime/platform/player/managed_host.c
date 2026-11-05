#include "managed_host.h"
#include <string.h>
extern unsigned long pthread_self(void);
static int owner(struct xw_managed_host *h){
 if(!h||!h->phase)return XW_PLAYER_INVALID;
 return h->busy||h->owner!=pthread_self()?XW_PLAYER_BUSY:0;
}
static void released(struct xw_managed_host *h,unsigned index){
 struct xw_player_session_offer *o=h->offers[index];
 if(o->channel.bound||o->player.backend){h->slots[index]=1;return;}
 if(!o->player.requests.session.serial){h->slots[index]=0;return;}
 struct xw_session_snapshot s;
 if(!xw_session_close_query(&h->manager,o->player.requests.session,&s)&&s.state==XW_SESSION_CLOSED)
  h->slots[index]=2; /* Locally verified release, safe fresh workspace reuse. */
 else h->slots[index]=3; /* Fault/unknown is never free space. */
}
int xw_managed_host_init(struct xw_managed_host *h,struct xw_player_broker *b,uint64_t generation,uint32_t supported,struct xw_player_session_offer **offers,unsigned count){
 if(!h||h->phase||!b||!generation||!supported||(supported&~7u)||!offers||!count||count>XW_SESSION_SLOTS)return XW_PLAYER_INVALID;
 for(unsigned i=0;i<count;i++){
  if(!offers[i]||offers[i]->channel.bound||offers[i]->player.backend||offers[i]->player.requests.session.serial)return XW_PLAYER_INVALID;
  for(unsigned j=0;j<i;j++)if(offers[i]==offers[j])return XW_PLAYER_INVALID;
 }
 if(xw_sessions_init(&h->manager,generation,supported))return XW_PLAYER_INVALID;
 for(unsigned i=0;i<count;i++)h->offers[i]=offers[i];
 int rc=xw_player_service_drain_init(&h->drain,&h->manager,b,h->offers,count);if(rc)return rc;
 h->count=count;h->owner=pthread_self();h->phase=XW_HOST_ACTIVE;return 0;
}
int xw_managed_host_offer(struct xw_managed_host *h,int delivery,uint32_t requested,uint32_t authorized,uint64_t now){
 int rc=owner(h);if(rc)return rc;if(h->phase!=XW_HOST_ACTIVE)return XW_PLAYER_CLOSED;
 h->busy=1;
 for(unsigned i=0;i<h->count;i++)if(h->slots[i]==0||h->slots[i]==2){
  if(h->slots[i]==2)memset(h->offers[i],0,sizeof *h->offers[i]);
  rc=xw_player_session_offer(h->offers[i],&h->manager,&h->drain.broker->player,delivery,requested,authorized,now);
  if(!rc){h->slots[i]=1;h->refreshed[i]=0;}else released(h,i);
  h->busy=0;return rc;
 }
 h->busy=0;return XW_PLAYER_BUSY;
}
int xw_managed_host_stop_dependency(struct xw_managed_host *h,void *context,int (*poll)(void *,uint64_t)){
 int rc=owner(h);if(rc)return rc;
 if(h->phase!=XW_HOST_ACTIVE||h->prepare.state)return XW_PLAYER_CLOSED;
 if(!poll||h->stop_poll)return XW_PLAYER_INVALID;
 h->stop_context=context;h->stop_poll=poll;return 0;
}
int xw_managed_host_stop(struct xw_managed_host *h,uint32_t reason){
 int rc=owner(h);if(rc)return rc;
 if(h->phase==XW_HOST_STOPPED)return 0;
 if(h->phase==XW_HOST_FAULT)return XW_PLAYER_UNAVAILABLE;
 if(h->phase==XW_HOST_STOPPING)return XW_PLAYER_BUSY;
 h->busy=1;rc=xw_player_service_drain_begin(&h->drain,reason);h->busy=0;
 h->phase=rc==XW_PLAYER_BUSY?XW_HOST_STOPPING:XW_HOST_FAULT;
 return rc==XW_PLAYER_BUSY?rc:XW_PLAYER_UNAVAILABLE;
}
int xw_managed_host_tick(struct xw_managed_host *h,uint64_t now){
 int rc=owner(h);if(rc)return rc;
 if(h->phase==XW_HOST_STOPPED)return 0;
 if(h->phase==XW_HOST_FAULT)return XW_PLAYER_UNAVAILABLE;
 h->busy=1;
 if(h->phase==XW_HOST_STOPPING){
  rc=h->prepare.state?xw_deferred_prepare_step(&h->prepare):xw_player_service_drain_step(&h->drain);
  if(!rc&&!h->prepare.state&&h->stop_poll)rc=h->stop_poll(h->stop_context,h->manager.generation);
  if(!rc)h->phase=XW_HOST_STOPPED;else if(rc!=XW_PLAYER_BUSY)h->phase=XW_HOST_FAULT;
  h->busy=0;return rc;
 }
 for(unsigned i=0;i<h->count;i++)if(h->slots[i]==1){
  struct xw_player_session_offer *o=h->offers[i];struct xw_session_snapshot s;
  if(o->channel.hello&&o->player.backend&&!xw_session_read(&h->manager,o->player.requests.session,&s)&&
     s.state==XW_SESSION_ACTIVE&&(s.grants&XW_PLAYER_GRANT_READ)&&
     (!h->refreshed[i]||now<h->refresh_at[i]||now-h->refresh_at[i]>=200)){
   h->refreshed[i]=1;h->refresh_at[i]=now;xw_managed_player_refresh(&o->player);
  }
  rc=xw_player_session_offer_tick(o,now);
  if(rc<0)h->last_client_error=rc;
  if(rc||!o->channel.bound)released(h,i);
 }
 h->busy=0;return 0;
}
int xw_managed_host_prepare(struct xw_managed_host *h,uint32_t reason,uint64_t epoch,void *context,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t)){
 int rc=owner(h);if(rc)return rc;
 /* A user-generation poll cannot be silently substituted for a qualified
  * native-epoch contract. Retain ownership if that integration is absent. */
 if(h->stop_poll&&!h->prepare.dependency)return XW_PLAYER_UNSUPPORTED;
 if(h->phase==XW_HOST_STOPPING&&h->prepare.state)return XW_PLAYER_BUSY;
 if(h->phase!=XW_HOST_ACTIVE&&h->phase!=XW_HOST_STOPPING)return XW_PLAYER_CLOSED;
 if(!epoch||!valid||!resume)return XW_PLAYER_INVALID;
 h->busy=1;
 rc=h->phase==XW_HOST_STOPPING?xw_deferred_prepare_adopt(&h->prepare,&h->drain,epoch,context,valid,resume):xw_deferred_prepare_begin(&h->prepare,&h->drain,reason,epoch,context,valid,resume);
 h->busy=0;
 if(rc!=XW_PLAYER_BUSY)xw_sessions_quiesce(&h->manager,reason);
 h->phase=rc==XW_PLAYER_BUSY?XW_HOST_STOPPING:XW_HOST_FAULT;
 return rc;
}
