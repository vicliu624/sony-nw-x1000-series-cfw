/* Real glue/view/deferred drain, modeled host resource decision and workers. */
#include "player_deferred_native.c"
#include "../../runtime/platform/player/host_prepare_bridge.h"
#include "../../runtime/platform/player/host_managed_service.h"
unsigned test_prepare_owned=1,test_exit_events,test_output_value,test_reentries;
int test_decision_error;
#ifdef XW_PLAYER_NATIVE_RF
int xw_player_host_service_stop(void){return 0;}
int xw_player_host_service_quiesce(void){return 0;}
unsigned test_radio_pending,test_radio_calls;
unsigned test_radio_unbound;
int xw_player_host_wireless_has_authority(void){return !test_radio_unbound;}
int xw_player_host_resources_idle(void){return test_prepare_owned?XW_PLAYER_BUSY:0;}
int xw_player_host_native_resources_idle(void){return test_prepare_owned?XW_PLAYER_BUSY:0;}
int xw_player_host_wireless_prepare_stop(uint64_t epoch){
 if(!epoch)return -1;test_radio_calls++;
 if(test_radio_unbound)return -5;
 if(test_radio_pending){test_radio_pending--;return 1;}return 0;
}
#endif
void xw_player_host_note_native_exit(void){test_exit_events++;}
int xw_player_host_exit_decision(uint64_t epoch,void *c,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t)){
 if(xw_player_prepare_intercept(0xdead0001,6,0xdead0001,17)!=XW_PREPARE_BRIDGE_HANDLED)return XW_HOST_EXIT_FACTORY;
 test_reentries++;
 if(test_decision_error)return test_decision_error;
 if(!test_prepare_owned)return XW_HOST_EXIT_FACTORY;
 if(!prepare.state){int rc=xw_deferred_prepare_begin(&prepare,&drain,XW_SESSION_SOURCE_LOST,epoch,c,valid,resume);if(rc!=XW_PLAYER_BUSY)xw_sessions_quiesce(&manager,XW_SESSION_SOURCE_LOST);}
 return XW_HOST_EXIT_HOLD;
}
int xw_host_pid_dispatch(uint32_t root,uint32_t command,uint32_t caller,uint32_t list,uint32_t output){
 (void)list;
 if(caller!=XW_PREPARE_BRIDGE_CALLER)return 4321;
 if(xw_test_thread!=17)return XW_PREPARE_BRIDGE_HANDLED;
 test_output_value=output;
 int rc=xw_player_prepare_intercept(root,command,output,17);
 return rc==XW_PREPARE_BRIDGE_HANDLED?rc:4321;
}
