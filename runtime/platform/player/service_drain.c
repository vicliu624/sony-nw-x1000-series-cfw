#include "service_drain.h"
static int fault(struct xw_player_service_drain *d,int error){d->phase=XW_DRAIN_FAULT;d->error=error;return XW_PLAYER_UNAVAILABLE;}
int xw_player_service_drain_init(struct xw_player_service_drain *d,struct xw_session_manager *m,struct xw_player_broker *b,struct xw_player_session_offer **offers,unsigned count){
 if(!d||d->phase||!m||!m->generation||!b||!b->backend||!b->backend->initialized||!b->player.initialized||b->backend==&b->player||b->player.provider.context!=b||count>XW_SESSION_SLOTS||(count&&!offers))return XW_PLAYER_INVALID;
 for(unsigned i=0;i<count;i++)if(!offers[i]||(offers[i]->player.backend&&offers[i]->player.manager!=m))return XW_PLAYER_INVALID;
 d->manager=m;d->broker=b;d->original=b->backend;d->offers=offers;d->count=count;d->phase=XW_DRAIN_READY;return 0;
}
int xw_player_service_drain_begin(struct xw_player_service_drain *d,uint32_t reason){
 if(!d||!d->phase)return XW_PLAYER_INVALID;if(d->phase==XW_DRAIN_FAULT)return XW_PLAYER_UNAVAILABLE;
 if(d->phase==XW_DRAIN_DONE)return 0;if(d->phase!=XW_DRAIN_READY)return XW_PLAYER_BUSY;
 int rc=xw_sessions_quiesce(d->manager,reason);if(rc==XW_SESSION_BUSY)return XW_PLAYER_BUSY;
 if(rc==XW_SESSION_INVALID)return XW_PLAYER_INVALID;
 d->phase=XW_DRAIN_SESSIONS;return XW_PLAYER_BUSY;
}
int xw_player_service_drain_step(struct xw_player_service_drain *d){
 if(!d||!d->phase||d->phase==XW_DRAIN_READY)return XW_PLAYER_INVALID;
 if(d->phase==XW_DRAIN_DONE)return 0;if(d->phase==XW_DRAIN_FAULT)return XW_PLAYER_UNAVAILABLE;
 if(!d->original->initialized||d->broker->backend!=d->original)return fault(d,XW_PLAYER_PROTOCOL);
 if(d->phase==XW_DRAIN_SESSIONS){
  for(unsigned i=0;i<d->count;i++){
   struct xw_player_session_offer *o=d->offers[i];int rc=0;
   if(o->channel.bound){rc=xw_managed_channel_close(&o->channel);if(rc==1)rc=0;}
   else if(o->player.backend)rc=xw_managed_player_close(&o->player);
   if(rc&&rc!=XW_PLAYER_BUSY)d->error=rc;
  }
  int rc=xw_sessions_drained(d->manager);if(d->error||rc==XW_SESSION_FAULT)return fault(d,d->error?d->error:rc);
  if(rc)return XW_PLAYER_BUSY;d->phase=XW_DRAIN_BACKEND;
 }
 int rc=xw_player_close(&d->broker->player);if(rc==XW_PLAYER_BUSY)return rc;if(rc)return fault(d,rc);
 if(!d->original->initialized||d->broker->backend)return fault(d,XW_PLAYER_PROTOCOL);
 d->phase=XW_DRAIN_DONE;return 0;
}
