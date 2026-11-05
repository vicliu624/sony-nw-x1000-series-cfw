#include "drain_completion.h"
int xw_drain_completion_arm(struct xw_drain_completion *c,struct xw_player_service_drain *d,uint64_t epoch,uint32_t token,void *context,int (*registered)(void *,uint64_t,uint32_t),int (*notify)(void *,uint64_t,uint32_t)){
 if(!c||c->state||!d||d->phase!=XW_DRAIN_SESSIONS||!epoch||!token||!registered||!notify)return XW_PLAYER_INVALID;
 if(registered(context,epoch,token)!=1)return XW_PLAYER_UNAVAILABLE;
 c->drain=d;c->epoch=epoch;c->token=token;c->context=context;c->registered=registered;c->notify=notify;c->state=XW_COMPLETION_ARMED;return 0;
}
int xw_drain_completion_step(struct xw_drain_completion *c){
 if(!c||!c->state)return XW_PLAYER_INVALID;
 if(c->state==XW_COMPLETION_CALLING)return XW_PLAYER_BUSY;
 if(c->state==XW_COMPLETION_DONE)return 0;if(c->state==XW_COMPLETION_FAULT)return XW_PLAYER_UNAVAILABLE;
 if(c->registered(c->context,c->epoch,c->token)!=1){c->state=XW_COMPLETION_FAULT;return XW_PLAYER_UNAVAILABLE;}
 int rc=xw_player_service_drain_step(c->drain);if(rc==XW_PLAYER_BUSY)return rc;
 if(rc||c->registered(c->context,c->epoch,c->token)!=1){c->state=XW_COMPLETION_FAULT;return XW_PLAYER_UNAVAILABLE;}
 /* Latch before callback: synchronous reentry or uncertain reply cannot cause
  * a second native completion invocation. No deadline fabricates completion. */
 c->state=XW_COMPLETION_CALLING;rc=c->notify(c->context,c->epoch,c->token);
 c->state=rc?XW_COMPLETION_FAULT:XW_COMPLETION_DONE;return rc?XW_PLAYER_UNCERTAIN:0;
}
