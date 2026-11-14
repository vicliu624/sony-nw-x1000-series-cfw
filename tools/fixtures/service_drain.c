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
struct revoked_adoption {
 struct xw_player_service_drain *drain;
 unsigned valid,forwards,retirement_polls;
};
static int adoption_valid(void *context,uint64_t epoch){struct revoked_adoption *a=context;assert(epoch==31);return a->valid;}
static int adoption_forward(void *context,uint64_t epoch){struct revoked_adoption *a=context;(void)epoch;a->forwards++;assert(0);return 0;}
static int adoption_retired(void *context,uint64_t epoch){
 struct revoked_adoption *a=context;assert(epoch==31&&a->drain->phase==XW_DRAIN_DONE&&!a->forwards);
 return ++a->retirement_polls<3?XW_PLAYER_BUSY:0;
}
struct completed_adoption {
 struct xw_player_service_drain *drain;
 unsigned valid,forwards,polls,revoke_during_poll;
};
static int completed_valid(void *context,uint64_t epoch){
 struct completed_adoption *a=context;assert(epoch==81);return a->valid;
}
static int completed_forward(void *context,uint64_t epoch){
 struct completed_adoption *a=context;assert(epoch==81&&a->valid&&a->polls==3);
 assert(a->drain->phase==XW_DRAIN_DONE&&!a->drain->broker->backend&&a->drain->original->initialized);
 a->forwards++;return 0;
}
static int completed_retired(void *context,uint64_t epoch){
 struct completed_adoption *a=context;assert(epoch==81&&a->drain->phase==XW_DRAIN_DONE&&!a->forwards);
 if(a->revoke_during_poll&&a->polls==1)a->valid=0;
 return ++a->polls<3?XW_PLAYER_BUSY:0;
}
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
  if(!i)assert(gate_managers[i].accepting&&gate_brokers[i].player.initialized&&gate_brokers[i].backend==&original);
  if(i)assert(xw_deferred_prepare_step(&gates[i])==(i==3?XW_PLAYER_UNCERTAIN:XW_PLAYER_UNAVAILABLE));
  unsigned checked=failure.checks;
  assert(xw_deferred_prepare_step(&gates[i])==XW_PLAYER_UNAVAILABLE&&failure.checks==checked&&failure.forwards==(i==3));
  assert(gates[i].state==((i==1||i==2)?XW_PREPARE_REVOKED_DONE:XW_PREPARE_FAULT)&&original.initialized);
 }
 static struct xw_player_broker adopt_broker;static struct xw_session_manager adopt_manager;
 static struct xw_player_service_drain adopt_drain;static struct xw_player_session_offer adopt_offer;
 static struct xw_deferred_prepare adopt_prepare;
 struct xw_player_provider adopt_provider={XW_PLAYER_API,0,&adopt_broker,snapshot,0,0,broker_close};
 adopt_broker.backend=&original;assert(!xw_player_bind(&adopt_broker.player,&adopt_provider));
 assert(!xw_sessions_init(&adopt_manager,30,1)&&!xw_session_open(&adopt_manager,1,1,&h));
 assert(!xw_managed_player_bind(&adopt_offer.player,&adopt_manager,h,&adopt_broker.player));
 struct xw_player_session_offer *adopt_offers[]={&adopt_offer};
 assert(!xw_player_service_drain_init(&adopt_drain,&adopt_manager,&adopt_broker,adopt_offers,1));
 struct revoked_adoption revoked={&adopt_drain,0,0,0};
 assert(!xw_deferred_prepare_dependency(&adopt_prepare,&revoked,adoption_retired));
 assert(xw_player_service_drain_begin(&adopt_drain,XW_SESSION_USB)==XW_PLAYER_BUSY);
 closes=0;
 assert(xw_deferred_prepare_adopt(&adopt_prepare,&adopt_drain,31,&revoked,adoption_valid,adoption_forward)==XW_PLAYER_BUSY);
 int adopted=XW_PLAYER_BUSY;
 for(unsigned i=0;i<10&&adopted==XW_PLAYER_BUSY;i++)adopted=xw_deferred_prepare_step(&adopt_prepare);
 assert(adopted==XW_PLAYER_UNAVAILABLE&&adopt_prepare.state==XW_PREPARE_REVOKED_DONE);
 assert(adopt_drain.phase==XW_DRAIN_DONE&&!adopt_broker.backend&&!adopt_broker.player.initialized);
 assert(!adopt_offer.player.backend&&!adopt_manager.accepting&&closes==3&&original.initialized);
 assert(revoked.retirement_polls==3&&!revoked.forwards);
 revoked.valid=1;
 assert(xw_deferred_prepare_step(&adopt_prepare)==XW_PLAYER_UNAVAILABLE&&!revoked.forwards);
 static struct xw_player_broker revoked_failure_broker;static struct xw_session_manager revoked_failure_manager;
 static struct xw_player_service_drain revoked_failure_drain;static struct xw_deferred_prepare revoked_failure_prepare;
 struct xw_player_provider revoked_failure_provider={XW_PLAYER_API,0,&revoked_failure_broker,snapshot,0,0,broker_close};
 revoked_failure_broker.backend=&original;assert(!xw_player_bind(&revoked_failure_broker.player,&revoked_failure_provider));
 assert(!xw_sessions_init(&revoked_failure_manager,32,1));
 assert(!xw_player_service_drain_init(&revoked_failure_drain,&revoked_failure_manager,&revoked_failure_broker,0,0));
 struct revoked_adoption failed_revocation={&revoked_failure_drain,0,0,0};
 assert(!xw_deferred_prepare_dependency(&revoked_failure_prepare,&failed_revocation,adoption_retired));
 assert(xw_player_service_drain_begin(&revoked_failure_drain,XW_SESSION_USB)==XW_PLAYER_BUSY);
 assert(xw_deferred_prepare_adopt(&revoked_failure_prepare,&revoked_failure_drain,31,&failed_revocation,adoption_valid,adoption_forward)==XW_PLAYER_BUSY);
 close_failure=1;
 assert(xw_deferred_prepare_step(&revoked_failure_prepare)==XW_PLAYER_UNAVAILABLE);
 assert(revoked_failure_drain.phase==XW_DRAIN_FAULT&&revoked_failure_broker.backend==&original);
 assert(revoked_failure_broker.player.initialized&&!failed_revocation.retirement_polls&&!failed_revocation.forwards);
 unsigned failure_closes=closes;
 close_failure=0;failed_revocation.valid=1;
 assert(xw_deferred_prepare_step(&revoked_failure_prepare)==XW_PLAYER_UNAVAILABLE&&closes==failure_closes);
 static struct xw_player_broker cancelled_brokers[3];
 static struct xw_session_manager cancelled_managers[3];
 static struct xw_player_service_drain cancelled_drains[3];
 static struct xw_deferred_prepare cancelled_prepares[3];
 for (unsigned i = 0; i < 3; i++) {
     struct xw_player_broker *b = &cancelled_brokers[i];
     struct xw_session_manager *m = &cancelled_managers[i];
     struct xw_player_service_drain *d = &cancelled_drains[i];
     struct xw_deferred_prepare *p = &cancelled_prepares[i];
     struct xw_player_provider provider = {XW_PLAYER_API, 0, b, snapshot, 0, 0, broker_close};
     b->backend = &original;
     closes = 0;
     close_failure = 0;
     assert(!xw_player_bind(&b->player, &provider) && !xw_sessions_init(m, 40 + i, 1));
     assert(!xw_player_service_drain_init(d, m, b, 0, 0));
     assert(xw_deferred_prepare_drain_only(p, d, 31) == XW_PLAYER_INVALID && !p->state);
     assert(!xw_sessions_stop_admission(m));
     assert(xw_deferred_prepare_drain_only(p, d, 31) == XW_PLAYER_INVALID && !p->state);
     assert(xw_player_service_drain_begin(d, XW_SESSION_USB) == XW_PLAYER_BUSY);
     if (i == 1) {
         int finished = XW_PLAYER_BUSY;
         for (unsigned n = 0; n < 10 && finished == XW_PLAYER_BUSY; n++)
             finished = xw_player_service_drain_step(d);
         assert(!finished && d->phase == XW_DRAIN_DONE);
     }
     struct revoked_adoption receipt = {d, 0, 0, 0};
     assert(!xw_deferred_prepare_dependency(p, &receipt, adoption_retired));
     assert(xw_deferred_prepare_drain_only(p, d, 31) == XW_PLAYER_BUSY);
     assert(!p->valid && !p->resume);
     assert(xw_deferred_prepare_drain_only(p, d, 32) == XW_PLAYER_BUSY && p->epoch == 31);
     close_failure = i == 2;
     int result = XW_PLAYER_BUSY;
     for (unsigned n = 0; n < 10 && result == XW_PLAYER_BUSY; n++)
         result = xw_deferred_prepare_step(p);
     assert(result == XW_PLAYER_UNAVAILABLE && original.initialized && !m->accepting);
     assert(p->state == (i == 2 ? XW_PREPARE_FAULT : XW_PREPARE_REVOKED_DONE));
     assert(receipt.retirement_polls == (i == 2 ? 0 : 3) && !receipt.forwards);
     assert((b->backend == &original) == (i == 2));
     unsigned closed_before_retry = closes;
     close_failure = 0;
     assert(xw_deferred_prepare_step(p) == XW_PLAYER_UNAVAILABLE && closes == closed_before_retry);
 }
 puts("Service drain: cancelled native exit finishes active/completed cleanup without a continuation");
 static struct xw_player_broker completed_brokers[7];
 static struct xw_session_manager completed_managers[7];
 static struct xw_player_service_drain completed_drains[7];
 static struct xw_deferred_prepare completed_prepares[7];
 static const char *completed_cases[]={"forward-after-dependency","revoked-before-adopt",
  "revoked-during-dependency","error-refused","retained-backend-refused",
  "retained-player-refused","open-admission-refused"};
 for(unsigned i=0;i<7;i++){
  struct xw_player_broker *b=&completed_brokers[i];
  struct xw_session_manager *m=&completed_managers[i];
  struct xw_player_service_drain *d=&completed_drains[i];
  struct xw_deferred_prepare *p=&completed_prepares[i];
  struct xw_player_provider provider={XW_PLAYER_API,0,b,snapshot,0,0,broker_close};
  b->backend=&original;closes=0;close_failure=0;
  assert(!xw_player_bind(&b->player,&provider)&&!xw_sessions_init(m,60+i,1));
  assert(!xw_player_service_drain_init(d,m,b,0,0));
  assert(xw_player_service_drain_begin(d,XW_SESSION_CLIENT_CLOSE)==XW_PLAYER_BUSY);
  int result=XW_PLAYER_BUSY;
  for(unsigned n=0;n<10&&result==XW_PLAYER_BUSY;n++)result=xw_player_service_drain_step(d);
  assert(!result&&d->phase==XW_DRAIN_DONE&&closes==3&&!m->accepting);
  struct completed_adoption continuation={d,i!=1,0,0,i==2};
  assert(!xw_deferred_prepare_dependency(p,&continuation,completed_retired));
  if(i==3)d->error=XW_PLAYER_IO;
  if(i==4)b->backend=&original;
  if(i==5)b->player.initialized=1;
  if(i==6)m->accepting=1;
  result=xw_deferred_prepare_adopt(p,d,81,&continuation,completed_valid,completed_forward);
  if(i>=3){
   assert(result==XW_PLAYER_INVALID&&!p->state&&!continuation.polls&&!continuation.forwards);
   printf("COMPLETED_ADOPTION_CASE %s\n",completed_cases[i]);
   continue;
  }
  assert(result==XW_PLAYER_BUSY);
  assert(xw_deferred_prepare_adopt(p,d,82,&continuation,completed_valid,completed_forward)==XW_PLAYER_BUSY&&p->epoch==81);
  for(unsigned n=0;n<10&&result==XW_PLAYER_BUSY;n++)result=xw_deferred_prepare_step(p);
  assert(result==(i?XW_PLAYER_UNAVAILABLE:0)&&continuation.polls==3&&continuation.forwards==(i==0));
  assert(p->state==(i?XW_PREPARE_REVOKED_DONE:XW_PREPARE_DONE)&&closes==3&&original.initialized);
  continuation.valid=1;
  assert(xw_deferred_prepare_step(p)==(i?XW_PLAYER_UNAVAILABLE:0));
  assert(continuation.polls==3&&continuation.forwards==(i==0)&&closes==3);
  printf("COMPLETED_ADOPTION_CASE %s\n",completed_cases[i]);
 }
 puts("Service drain: completed SDK cleanup supports a fresh native dependency, with revocation and retained/faulted-state refusal");
 puts("Service drain: revoked continuation still drains adopted resources and retirement without native forwarding");
 puts("Service drain: revoke clients before broker, pending close, one completion and borrowed original preservation passed");return 0;
}
