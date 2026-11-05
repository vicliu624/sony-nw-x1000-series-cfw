#include "host_prepare_bridge.h"
#include "host_managed_service.h"
#include "stock_prepare_view.h"
static struct xw_stock_prepare_view view;
static struct {uint32_t root,command;unsigned long owner;uint64_t epoch;unsigned code_valid,native_free;} context;
static uint64_t serial;
static unsigned held,busy;
#ifdef XW_PLAYER_NATIVE_RF
#include "wireless_host.h"
static unsigned waiting_wireless;
static unsigned factory_delegated;
static void note_factory_delegation(void){
 if(context.command==3&&!xw_player_host_native_resources_idle()){
  factory_delegated=1;held=0;
 }
}
#endif
extern unsigned long pthread_self(void);
static int valid(void *c,uint64_t epoch){
 if(c!=&context||!epoch||epoch!=context.epoch||!context.code_valid)return 0;
#ifdef XW_PLAYER_NATIVE_RF
 if(context.native_free)return context.command==3&&context.root==0x613e60u&&
  pthread_self()==context.owner&&!xw_player_host_native_resources_idle()&&
  !xw_stock_prepare_code_check();
#endif
 if(!view.bound)return xw_stock_prepare_view_bind(&view,context.root,context.command,epoch,context.owner)==0;
 return xw_stock_prepare_view_check(&view,epoch)==0;
}
static int resume(void *c,uint64_t epoch){
 if(!valid(c,epoch))return XW_PLAYER_UNAVAILABLE;
 uint32_t output=0;
#ifdef XW_PLAYER_NATIVE_RF
 note_factory_delegation();
#endif
 return ((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x112fcu)(context.root,context.command,&output);
}
void xw_player_prepare_tick(void){
#ifdef XW_PLAYER_NATIVE_RF
 if(!waiting_wireless||busy||pthread_self()!=context.owner)return;
 busy=1;
 if(!valid(&context,context.epoch)){waiting_wireless=0;busy=0;return;}
 int rc=xw_player_host_wireless_prepare_stop(context.epoch);
 if(rc==XW_MODE_PENDING){busy=0;return;}
 waiting_wireless=0;
 if(!rc){
  int decision=xw_player_host_exit_decision(context.epoch,&context,valid,resume);
  if(decision==XW_HOST_EXIT_FACTORY)(void)resume(&context,context.epoch);
 }
 busy=0;
#endif
}
int xw_player_prepare_intercept(uint32_t root,uint32_t command,uint32_t output_value,unsigned long original_owner){
 (void)output_value;
 if(held||busy||!original_owner||pthread_self()!=original_owner)return XW_PREPARE_BRIDGE_HANDLED;
 busy=1;
#ifdef XW_PLAYER_NATIVE_RF
 /* Admission stays closed after native exit starts. Repeated original
  * preparation reuses the retired epoch, never a new admission or drain. */
 if(factory_delegated){
  int allowed=command==3&&root==context.root&&original_owner==context.owner&&
   !xw_player_host_native_resources_idle()&&!xw_stock_prepare_code_check()&&
   xw_player_host_wireless_has_authority()&&
   !xw_player_host_wireless_prepare_stop(context.epoch);
  if(!allowed)held=1;busy=0;return allowed?0:XW_PREPARE_BRIDGE_HANDLED;
 }
 /* A resource-free SDK with no radio authority has nothing to retire.
  * Requiring wireless prepare_stop would return DENIED and consume Sony's
  * command3 forever, preventing the ordinary Homebrew application switch. */
 if(command==3&&!xw_player_host_wireless_has_authority()&&!xw_player_host_native_resources_idle()){
  xw_player_host_note_native_exit();busy=0;return 0;
 }
#endif
 context.root=root;context.command=command;context.owner=original_owner;
 context.epoch=serial==UINT64_MAX?0:++serial;
 context.code_valid=xw_stock_prepare_code_check()==0;
#ifdef XW_PLAYER_NATIVE_RF
 /* Sony's pending-token list belongs to Sony. With no SDK resources there
  * is no deferred continuation whose Root snapshot must be retained. Keep
  * code/Root identity checks, but do not require native pending work to vanish
  * before Sony can process its own preparation request. */
 int empty=command==3&&!xw_player_host_native_resources_idle();
 context.native_free=empty;
 if(!context.code_valid||root!=0x613e60u||(!empty&&!valid(&context,context.epoch))){xw_player_host_note_native_exit();held=1;busy=0;return XW_PREPARE_BRIDGE_HANDLED;}
 int sdk=xw_player_host_service_quiesce();xw_player_host_note_native_exit();
 if(sdk&&sdk!=XW_PLAYER_BUSY){held=1;busy=0;return XW_PREPARE_BRIDGE_HANDLED;}
 int radio=xw_player_host_wireless_prepare_stop(context.epoch);
 if(radio){
  waiting_wireless=radio==XW_MODE_PENDING;held=1;busy=0;return XW_PREPARE_BRIDGE_HANDLED;
 }
 if(empty){
  note_factory_delegation();xw_stock_prepare_view_unbind(&view);busy=0;return 0;
 }
#else
 xw_player_host_note_native_exit();
#endif
 int decision=xw_player_host_exit_decision(context.epoch,&context,valid,resume);
 if(decision!=XW_HOST_EXIT_FACTORY){held=1;busy=0;return XW_PREPARE_BRIDGE_HANDLED;}
#ifdef XW_PLAYER_NATIVE_RF
 note_factory_delegation();
#endif
 xw_stock_prepare_view_unbind(&view);busy=0;return 0;
}
