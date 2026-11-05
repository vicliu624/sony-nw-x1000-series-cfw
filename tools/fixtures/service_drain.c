#include "../../runtime/platform/player/service_drain.h"
#include "../../runtime/platform/player/drain_completion.h"
#include "../../runtime/platform/player/deferred_prepare.h"
#include <assert.h>
#include <stdio.h>
static unsigned closes;
static int close_failure;
static unsigned notifications;
static struct xw_deferred_prepare deferred;
static unsigned resumed;
static unsigned dependency_polls;
static int dependency(void *context,uint64_t epoch){
 struct xw_player_service_drain *d=context;assert(epoch==9&&d->phase==XW_DRAIN_DONE);
 assert(!resumed&&xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY);
 return ++dependency_polls<3?XW_PLAYER_BUSY:0;
}
static int valid_prepare(void *context,uint64_t epoch){(void)context;assert(epoch==9);assert(xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY);return 1;}
static int resume_prepare(void *context,uint64_t epoch){struct xw_player_service_drain *d=context;assert(epoch==9&&d->phase==XW_DRAIN_DONE&&d->original->initialized&&!d->broker->player.initialized);assert(xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY);resumed++;return 0;}
struct prepare_failure {unsigned checks,allowed,forwards;int result;};
static int check_failure(void *context,uint64_t epoch){struct prepare_failure *f=context;assert(epoch==10);return ++f->checks<=f->allowed;}
static int forward_failure(void *context,uint64_t epoch){struct prepare_failure *f=context;assert(epoch==10);f->forwards++;return f->result;}
static int dependency_failure(void *context,uint64_t epoch){(void)context;assert(epoch==10);return XW_PLAYER_IO;}
static int registered(void *context,uint64_t epoch,uint32_t token){(void)context;assert(epoch==2&&token==0x456);return 1;}
static int uncertain(void *context,uint64_t epoch,uint32_t token){(void)context;assert(epoch==2&&token==0x456);notifications++;return XW_PLAYER_IO;}
static int snapshot(void *context,struct xw_player_snapshot *out){(void)context;out->valid=XW_PF_STATE;out->state=XW_PLAY_PLAYING;return 0;}
static int original_close(void *c){(void)c;assert(0);return 0;}
static int broker_close(void *context){struct xw_player_broker *b=context;closes++;if(close_failure)return XW_PLAYER_IO;if(closes<3)return XW_PLAYER_BUSY;b->backend=0;return 0;}
int main(void){
 static struct xw_player original;static struct xw_player_broker broker;static struct xw_session_manager manager;static struct xw_player_session_offer offer;static struct xw_player_service_drain drain;
 struct xw_player_provider original_provider={XW_PLAYER_API,0,0,snapshot,0,0,original_close};assert(!xw_player_bind(&original,&original_provider));
 struct xw_player_provider broker_provider={XW_PLAYER_API,0,&broker,snapshot,0,0,broker_close};broker.backend=&original;assert(!xw_player_bind(&broker.player,&broker_provider));
 struct xw_session_handle h;assert(!xw_sessions_init(&manager,3,1)&&!xw_session_open(&manager,1,1,&h)&&!xw_managed_player_bind(&offer.player,&manager,h,&broker.player));
 struct xw_player_session_offer *offers[]={&offer};assert(!xw_player_service_drain_init(&drain,&manager,&broker,offers,1));
 assert(!xw_deferred_prepare_dependency(&deferred,&drain,dependency));
 assert(xw_deferred_prepare_begin(&deferred,&drain,XW_SESSION_USB,9,&drain,valid_prepare,resume_prepare)==XW_PLAYER_BUSY&&!manager.accepting);
 assert(xw_deferred_prepare_begin(&deferred,&drain,XW_SESSION_USB,9,&drain,valid_prepare,resume_prepare)==XW_PLAYER_BUSY);
 assert(xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY&&closes==1&&!offer.player.backend&&original.initialized&&!resumed);
 assert(xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY&&closes==2&&original.initialized&&!resumed);
 assert(xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY&&closes==3&&dependency_polls==1&&!resumed);
 assert(xw_deferred_prepare_step(&deferred)==XW_PLAYER_BUSY&&closes==3&&dependency_polls==2&&!resumed);
 assert(!xw_deferred_prepare_step(&deferred)&&closes==3&&dependency_polls==3&&drain.phase==XW_DRAIN_DONE&&!broker.player.initialized&&original.initialized&&resumed==1);
 assert(!xw_deferred_prepare_step(&deferred)&&closes==3&&resumed==1);
 static struct xw_player_broker failed_broker;static struct xw_session_manager failed_manager;static struct xw_player_service_drain failed_drain;
 struct xw_player_provider failing={XW_PLAYER_API,0,&failed_broker,snapshot,0,0,broker_close};failed_broker.backend=&original;
 assert(!xw_player_bind(&failed_broker.player,&failing)&&!xw_sessions_init(&failed_manager,4,1));
 assert(!xw_player_service_drain_init(&failed_drain,&failed_manager,&failed_broker,0,0));close_failure=1;
 assert(xw_player_service_drain_begin(&failed_drain,XW_SESSION_SLEEP)==XW_PLAYER_BUSY);
 assert(xw_player_service_drain_step(&failed_drain)==XW_PLAYER_UNAVAILABLE&&failed_drain.phase==XW_DRAIN_FAULT&&original.initialized);
 unsigned failed_calls=closes;assert(xw_player_service_drain_step(&failed_drain)==XW_PLAYER_UNAVAILABLE&&closes==failed_calls);
 static struct xw_player_broker notify_broker;static struct xw_session_manager notify_manager;static struct xw_player_service_drain notify_drain;static struct xw_drain_completion completion;
 struct xw_player_provider notifying={XW_PLAYER_API,0,&notify_broker,snapshot,0,0,broker_close};notify_broker.backend=&original;close_failure=0;
 assert(!xw_player_bind(&notify_broker.player,&notifying)&&!xw_sessions_init(&notify_manager,5,1));
 assert(!xw_player_service_drain_init(&notify_drain,&notify_manager,&notify_broker,0,0));
 assert(xw_player_service_drain_begin(&notify_drain,XW_SESSION_USB)==XW_PLAYER_BUSY);
 assert(!xw_drain_completion_arm(&completion,&notify_drain,2,0x456,0,registered,uncertain));
 assert(xw_drain_completion_step(&completion)==XW_PLAYER_UNCERTAIN&&notifications==1&&completion.state==XW_COMPLETION_FAULT);
 assert(xw_drain_completion_step(&completion)==XW_PLAYER_UNAVAILABLE&&notifications==1&&original.initialized);
 static struct xw_player_broker gate_brokers[5];static struct xw_session_manager gate_managers[5];
 static struct xw_player_service_drain gate_drains[5];static struct xw_deferred_prepare gates[5];
 for(unsigned i=0;i<5;i++){
  struct prepare_failure failure={0,i==0?0:i==1?1:i==2?2:100,0,XW_PLAYER_IO};
  struct xw_player_provider bp={XW_PLAYER_API,0,&gate_brokers[i],snapshot,0,0,broker_close};
  gate_brokers[i].backend=&original;assert(!xw_player_bind(&gate_brokers[i].player,&bp));
  assert(!xw_sessions_init(&gate_managers[i],20+i,1));
  assert(!xw_player_service_drain_init(&gate_drains[i],&gate_managers[i],&gate_brokers[i],0,0));
  if(i==4)assert(!xw_deferred_prepare_dependency(&gates[i],0,dependency_failure));
  int rc=xw_deferred_prepare_begin(&gates[i],&gate_drains[i],XW_SESSION_USB,10,&failure,check_failure,forward_failure);
  assert(rc==(i==0?XW_PLAYER_UNAVAILABLE:XW_PLAYER_BUSY));
  if(i)assert(xw_deferred_prepare_step(&gates[i])==(i==3?XW_PLAYER_UNCERTAIN:XW_PLAYER_UNAVAILABLE));
  unsigned checked=failure.checks;
  assert(xw_deferred_prepare_step(&gates[i])==XW_PLAYER_UNAVAILABLE&&failure.checks==checked&&failure.forwards==(i==3));
  assert(gates[i].state==XW_PREPARE_FAULT&&original.initialized);
 }
 puts("Service drain: revoke clients before broker, pending close, one completion and borrowed original preservation passed");return 0;
}
