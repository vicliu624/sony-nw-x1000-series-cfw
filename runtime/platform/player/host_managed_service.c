#include "host_managed_service.h"
#include "host_hook.h"
#include "host_queue.h"
#include "managed_host.h"
#include "../../store/deadline.h"
#include <string.h>
#ifdef XW_PLAYER_NATIVE_RF
#include "wireless_host.h"
#endif
#ifdef XW_PLAYER_NATIVE_PREPARE
#include "stock_play_mode.h"
static struct xw_stock_play_mode native_mode;
#endif
extern unsigned long pthread_self(void);
static struct xw_player *original;
static unsigned long owner;
static unsigned dispatching;
static unsigned exit_held;
static unsigned native_exit_seen;
static struct xw_player_broker broker;
static struct xw_managed_host host;
/* One remote controller workspace by default; not an unbounded allocation. */
static struct xw_player_session_offer offer;
static struct {
 void *context;int (*request)(void *,uint64_t);
 void (*poll)(void *);
 uint64_t serial,pending,current,completed;
 int result;unsigned busy;
} settings;
__attribute__((weak)) int xw_player_host_source_attach(struct xw_player_broker *b){(void)b;return XW_PLAYER_UNSUPPORTED;}
__attribute__((weak)) void xw_player_host_inherited_tick(void){}
__attribute__((weak)) void xw_player_host_inherited_cancel(void){}
static int on_owner(void){return original&&owner==pthread_self()&&!dispatching;}
int xw_player_host_settings_bind(void *context,int (*request)(void *,uint64_t)){
 return xw_player_host_settings_bind_backend(context,request,0);
}
int xw_player_host_settings_bind_backend(void *context,int (*request)(void *,uint64_t),void (*poll)(void *)){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
 if(!request)return XW_PLAYER_INVALID;
 if(settings.request||settings.pending||settings.busy)return XW_PLAYER_BUSY;
 settings.context=context;settings.request=request;settings.poll=poll;return 0;
}
int xw_player_host_settings_enqueue(void){
 if(!on_owner())return XW_PLAYER_BUSY;
#ifdef XW_PLAYER_NATIVE_RF
 if(!xw_player_host_wireless_player_active())return XW_PLAYER_CLOSED;
#endif
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
 if(!settings.request)return XW_PLAYER_UNAVAILABLE;
 if(settings.pending||settings.busy)return XW_PLAYER_BUSY;
 if(settings.serial==UINT64_MAX)return XW_PLAYER_UNAVAILABLE;
 settings.pending=++settings.serial;return XW_PLAYER_ACCEPTED;
}
int xw_player_host_settings_result(uint64_t serial,int *result){
 if(!result||!serial)return XW_PLAYER_INVALID;
 if(!on_owner())return XW_PLAYER_BUSY;
 if(serial==settings.pending||(settings.busy&&serial==settings.current))return XW_PLAYER_BUSY;
 if(serial!=settings.completed)return XW_PLAYER_STALE;
 *result=settings.result;return 0;
}
int xw_player_host_settings_unbind(void){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(settings.pending||settings.busy)return XW_PLAYER_BUSY;
 settings.context=0;settings.request=0;settings.poll=0;return 0;
}
static void settings_pump(void){
 if(settings.busy)return;
 if(settings.poll){settings.busy=1;settings.poll(settings.context);settings.busy=0;}
#ifdef XW_PLAYER_NATIVE_RF
 if(!xw_player_host_wireless_player_active()){
  if(settings.pending){settings.completed=settings.pending;settings.result=XW_PLAYER_CLOSED;settings.pending=0;}
  return;
 }
#endif
 if(exit_held||native_exit_seen)return;
 if(!settings.pending||settings.busy||!settings.request)return;
 uint64_t serial=settings.pending;settings.pending=0;settings.current=serial;settings.busy=1;
 int rc=settings.request(settings.context,serial);
 settings.result=(native_exit_seen||exit_held)?XW_PLAYER_CLOSED:rc;
 settings.completed=serial;settings.current=0;settings.busy=0;
}
static int mode_read(void *context,uint32_t *native,uint32_t *index){
 if(context!=original||!original||!original->initialized||owner!=pthread_self()||exit_held||native_exit_seen)return XW_PLAYER_UNAVAILABLE;
#ifdef XW_PLAYER_NATIVE_PREPARE
 if(!native_mode.bound){int rc=xw_stock_play_mode_bind(&native_mode,owner);if(rc)return rc;}
 return xw_stock_play_mode_read(&native_mode,native,index);
#else
 (void)native;(void)index;return XW_PLAYER_UNSUPPORTED;
#endif
}
unsigned xw_player_host_service_phase(void){return on_owner()?host.phase:0;}
int xw_player_host_original_exiting(void){return !on_owner()||exit_held||native_exit_seen;}
static int resources_idle(void){
 if(!original->initialized)return XW_PLAYER_UNAVAILABLE;
 if(host.phase&&host.phase!=XW_HOST_STOPPED)return host.phase==XW_HOST_FAULT?XW_PLAYER_UNAVAILABLE:XW_PLAYER_BUSY;
 if(host.prepare.state||broker.backend||broker.player.initialized||broker.metadata.initialized||broker.library.worker.initialized||broker.queue.context||broker.source.context||offer.channel.bound||offer.player.backend)return XW_PLAYER_UNAVAILABLE;
 return 0;
}
int xw_player_host_resources_idle(void){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
 return resources_idle();
}
int xw_player_host_native_resources_idle(void){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held)return XW_PLAYER_CLOSED;
 return resources_idle();
}
int xw_player_host_next_generation(uint64_t *out){
 if(!out)return XW_PLAYER_INVALID;
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
#ifdef XW_PLAYER_NATIVE_RF
 if(!xw_player_host_wireless_player_active())return XW_PLAYER_CLOSED;
#endif
 int idle=resources_idle();if(idle)return idle;
 if(host.manager.generation==UINT64_MAX)return XW_PLAYER_UNAVAILABLE;
 *out=host.manager.generation+1;return 0;
}
int xw_player_host_generation_retired(uint64_t generation){
 if(!generation)return XW_PLAYER_INVALID;
 if(!on_owner())return XW_PLAYER_BUSY;
 if(host.manager.generation>generation)return 1;
 return host.manager.generation==generation&&host.phase==XW_HOST_STOPPED;
}
int xw_player_host_service_stop_generation(uint64_t generation){
 if(!generation)return XW_PLAYER_INVALID;
 if(!on_owner())return XW_PLAYER_BUSY;
 if(host.manager.generation!=generation)return XW_PLAYER_STALE;
 if(native_exit_seen&&!exit_held&&!host.prepare.state){
  if(host.prepare.dependency&&!host.stop_poll)return XW_PLAYER_UNSUPPORTED;
  if(host.phase==XW_HOST_STOPPED)return 0;
  return xw_managed_host_stop(&host,XW_SESSION_SOURCE_LOST);
 }
 return xw_player_host_service_stop();
}
int xw_player_host_service_quiesce(void){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
 if(!host.phase||host.phase==XW_HOST_STOPPED)return 0;
 if(host.phase==XW_HOST_FAULT)return XW_PLAYER_UNAVAILABLE;
 if(host.phase==XW_HOST_STOPPING)return 0;
 int rc=xw_sessions_stop_admission(&host.manager);
 return rc==XW_SESSION_BUSY?XW_PLAYER_BUSY:rc?XW_PLAYER_UNAVAILABLE:0;
}
int xw_player_host_exit_dependency(void *context,int (*poll)(void *,uint64_t)){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen||host.phase!=XW_HOST_ACTIVE)return XW_PLAYER_CLOSED;
 return xw_deferred_prepare_dependency(&host.prepare,context,poll);
}
int xw_player_host_session_offer(int delivery,uint32_t requested,uint32_t authorized,uint64_t generation){
 if(!on_owner())return XW_PLAYER_BUSY;
#ifdef XW_PLAYER_NATIVE_RF
 if(!xw_player_host_wireless_player_active())return XW_PLAYER_CLOSED;
#endif
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
 if(!generation||!requested||(requested&~7u)||(requested&~authorized)||delivery<0)return XW_PLAYER_INVALID;
 if(!original->initialized)return XW_PLAYER_UNAVAILABLE;
 unsigned long long now;if(hb_monotonic_millis(&now))return XW_PLAYER_UNAVAILABLE;
 if(host.phase==XW_HOST_STOPPING)return XW_PLAYER_CLOSED;
 if(host.phase==XW_HOST_STOPPED){
  /* A user switch may retire the SDK while Sony playback stays alive. Only a
   * proved ordinary drain permits a new generation; native-exit continuations
   * and retained/faulted resources are never reset into apparent free space. */
  if(generation<=host.manager.generation)return XW_PLAYER_STALE;
  if(host.prepare.state||broker.backend||broker.player.initialized||
     broker.metadata.initialized||broker.library.worker.initialized||
     broker.queue.context||broker.source.context||offer.channel.bound||offer.player.backend)
   return XW_PLAYER_UNAVAILABLE;
  memset(&host,0,sizeof host);memset(&offer,0,sizeof offer);memset(&broker,0,sizeof broker);
 }
 if(!host.phase){
  int rc=broker.player.initialized?0:xw_player_broker_bind(&broker,original);if(rc)return rc;
  struct xw_player_session_offer *slots[]={&offer};
  rc=xw_managed_host_init(&host,&broker,generation,7,slots,1);
  if(rc){xw_player_close(&broker.player);return rc;}
 }
 if(generation!=host.manager.generation)return XW_PLAYER_STALE;
 int rc=xw_managed_host_offer(&host,delivery,requested,authorized,now);
 if(!rc){int bound=xw_managed_player_mode_bind(&offer.player,original,mode_read);if(bound)host.last_client_error=bound;}
 return rc;
}
int xw_player_host_stop_dependency(void *context,int (*poll)(void *,uint64_t)){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen)return XW_PLAYER_CLOSED;
 return xw_managed_host_stop_dependency(&host,context,poll);
}
int xw_player_host_service_stop(void){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(exit_held||native_exit_seen||host.prepare.state)return XW_PLAYER_CLOSED;
 /* The native-exit dependency takes a qualified native epoch. A plain user
  * switch has no such epoch and must not discard that retirement contract. */
 if(host.prepare.dependency&&!host.stop_poll)return XW_PLAYER_UNSUPPORTED;
 if(!host.phase||host.phase==XW_HOST_STOPPED)return 0;
 return xw_managed_host_stop(&host,XW_SESSION_CLIENT_CLOSE);
}
int xw_player_host_prepare_exit(uint64_t epoch,void *context,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t)){
 if(!on_owner())return XW_PLAYER_BUSY;
 if(!host.phase)return XW_PLAYER_CLOSED;
 return xw_managed_host_prepare(&host,XW_SESSION_SOURCE_LOST,epoch,context,valid,resume);
}
void xw_player_host_note_native_exit(void){native_exit_seen=1;xw_player_host_inherited_cancel();
 if(settings.pending){settings.completed=settings.pending;settings.result=XW_PLAYER_CLOSED;settings.pending=0;}
#ifdef XW_PLAYER_NATIVE_PREPARE
 (void)xw_stock_play_mode_unbind(&native_mode);
#endif
}
int xw_player_host_exit_decision(uint64_t epoch,void *context,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t)){
 if(!original)return XW_HOST_EXIT_FACTORY;
 if(!on_owner())return XW_HOST_EXIT_HOLD;
 if(exit_held||host.prepare.state)return XW_HOST_EXIT_HOLD;
 if(!host.phase){
  if(!broker.backend&&!broker.player.initialized&&!broker.metadata.initialized&&!broker.library.worker.initialized&&!broker.queue.context&&!broker.source.context)return XW_HOST_EXIT_FACTORY;
  exit_held=1;return XW_HOST_EXIT_HOLD; /* Unreleased partial initialization. */
 }
 if(host.phase==XW_HOST_STOPPED)return XW_HOST_EXIT_FACTORY;
 exit_held=1;
 int rc=xw_player_host_prepare_exit(epoch,context,valid,resume);
 if(rc!=XW_PLAYER_BUSY){
  xw_sessions_quiesce(&host.manager,XW_SESSION_SOURCE_LOST);
  host.phase=XW_HOST_FAULT;
 }
 return XW_HOST_EXIT_HOLD;
}
void xw_player_host_dispatch(struct xw_player *player){
 if(!player)return;
 if(!original){if(!player->initialized)return;original=player;owner=pthread_self();}
 if(player!=original||owner!=pthread_self()||dispatching)return;
 if(!exit_held&&!native_exit_seen){xw_player_host_inherited_tick();settings_pump();}
 if(!host.phase||host.phase==XW_HOST_STOPPED)return;
 dispatching=1;
 if(!original->initialized){
  xw_managed_host_stop(&host,XW_SESSION_SOURCE_LOST);
  xw_managed_host_tick(&host,0);dispatching=0;return;
 }
 unsigned long long now;
 if(hb_monotonic_millis(&now)){
  xw_managed_host_stop(&host,XW_SESSION_SOURCE_LOST);
  xw_managed_host_tick(&host,0);
 }else{
  if(host.phase==XW_HOST_ACTIVE){
   if(!broker.queue.browse)xw_player_host_queue_attach(&broker);
   if(!broker.source.command)xw_player_host_source_attach(&broker);
   xw_player_broker_tick(&broker,now);
  }
  xw_managed_host_tick(&host,now);
 }
 dispatching=0;
}
