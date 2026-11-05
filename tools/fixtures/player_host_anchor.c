/* Strong owner-dispatch probe; no sockets, worker or device operations. */
#include "stock_provider_host.c"
unsigned test_resolve=1,test_pid_calls,test_dispatch_calls,test_initialized;
#ifdef XW_PLAYER_NATIVE_SLEEP
unsigned test_sleep_begins,test_sleep_polls;
unsigned test_sleep_restore_begins,test_sleep_restore_completes,test_sleep_restore_result;
int xw_player_sleep_native_restore_begin(uint32_t root,unsigned long owner){if(root!=0x613e60||owner!=17)return -1;test_sleep_restore_begins++;return 0;}
int xw_player_sleep_native_restore_complete(int result,unsigned long owner){if(owner!=17)return -1;test_sleep_restore_completes++;test_sleep_restore_result=result;return 0;}
unsigned test_sleep_unbound,test_sleep_busy;
unsigned test_sleep_inactive;
int xw_player_sleep_native_inactive(void){return test_sleep_inactive?0:-2;}
int xw_player_host_resources_idle(void){return test_sleep_busy?-4:0;}
int xw_player_host_wireless_has_authority(void){return !test_sleep_unbound;}
int xw_player_host_next_generation(uint64_t *generation){if(test_sleep_busy)return -4;*generation=1;return 0;}
int xw_player_sleep_native_begin(uint32_t callsite,unsigned long owner){if((callsite!=0x61c5c&&callsite!=0x61648&&callsite!=0x614f0&&callsite!=0x61940)||owner!=17)return -1;test_sleep_begins++;return 1;}
int xw_player_sleep_native_poll(void){test_sleep_polls++;return 1;}
#endif
int test_errno=1234,test_poll_result;
#ifdef XW_PLAYER_REMOTE_FACTORY
unsigned test_factory_ticks;
void xw_player_host_remote_auto(void){test_factory_ticks++;}
#endif
static int test_real_pid(void){test_pid_calls++;return 4321;}
void *dlsym(void *handle,const char *name){return test_resolve&&handle==(void *)(intptr_t)-1&&!strcmp(name,"getpid")?(void *)test_real_pid:0;}
int *__errno_location(void){return &test_errno;}
#ifdef XW_PLAYER_NATIVE_RF
#include "../../runtime/platform/player/wireless_host.h"
#ifndef XW_PLAYER_NATIVE_SLEEP
unsigned test_sleep_unbound,test_sleep_busy;
int xw_player_host_wireless_has_authority(void){return !test_sleep_unbound;}
int xw_player_host_resources_idle(void){return test_sleep_busy?-4:0;}
#endif
unsigned test_rf_allowed,test_rf_permissions;
int test_rf_cleanup_mode;unsigned test_rf_cleanup_permissions;
int xw_native_rf_cleanup_permission(void){test_rf_cleanup_permissions++;test_errno=99;return test_rf_cleanup_mode;}
extern unsigned long xw_test_thread;
int xw_native_rf_gui_owner(void){return xw_test_thread==17;}
int xw_native_rf_permission(void){test_rf_permissions++;test_errno=99;return test_rf_allowed?0:-1;}
unsigned test_rf_worker_entries;
int xw_native_rf_bootstrap_worker(void){test_rf_worker_entries++;test_errno=99;return 0;}
unsigned test_wireless_ticks,test_wireless_bounds;
int xw_player_host_wireless_prepare_stop(uint64_t epoch){return epoch?0:-1;}
int xw_player_host_wireless_next_epoch(uint64_t *epoch){static uint64_t serial;if(test_sleep_unbound)return XW_MODE_DENIED;*epoch=++serial;return 0;}
int xw_player_host_wireless_prepare_handoff(uint64_t epoch){return epoch?0:-1;}
int xw_player_host_wireless_resume_handoff(uint64_t epoch){return epoch?0:-1;}
int xw_player_host_service_stop(void){return 0;}
int xw_player_host_service_quiesce(void){return 0;}
int xw_player_host_wireless_bound(struct xw_wireless_mode_policy *p){(void)p;test_wireless_bounds++;return 0;}
int xw_player_host_wireless_tick(void){test_wireless_ticks++;test_errno=99;return 0;}
unsigned test_wireless_requests,test_wireless_event;
int xw_player_host_wireless_request(uint32_t event){test_wireless_requests++;test_wireless_event=event;test_errno=99;return 0;}
unsigned test_poweroff_notes;int test_poweroff_result;
int xw_native_rf_poweroff_note(int result){test_poweroff_notes++;test_poweroff_result=result;test_errno=99;return 0;}
unsigned test_disable_checks,test_disable_event;
int xw_native_rf_disable_checkpoint(uint32_t event){test_disable_checks++;test_disable_event=event;test_errno=99;return 0;}
#endif
#ifdef XW_PLAYER_NATIVE_WIRELESS_SETTINGS
#include "../../runtime/platform/wireless/mode_policy.h"
#include "../../runtime/platform/player/host_hook.h"
static struct xw_wireless_mode_policy test_wireless_policy;
int test_wireless_bind(void){
 int rc=xw_mode_policy_init(&test_wireless_policy,77);if(rc)return rc;
 rc=xw_mode_policy_confirm_off(&test_wireless_policy,XW_WIRELESS_MODE_OFF,1);if(rc)return rc;
 return xw_player_host_wireless_bind(&test_wireless_policy);
}
int test_wireless_mode(void){return xw_mode_policy_admitted(&test_wireless_policy);}
#endif
#ifdef XW_PLAYER_NATIVE_REMOTE_SETTINGS
unsigned test_settings_requests;
int xw_player_host_settings_enqueue(void){test_settings_requests++;test_errno=99;return XW_PLAYER_ACCEPTED;}
#endif
void xw_player_host_dispatch(struct xw_player *player)
{
    struct xw_player_snapshot snapshot;
    test_dispatch_calls++;test_initialized=player->initialized;
    test_poll_result=xw_player_snapshot(player,&snapshot);
}

unsigned test_met_calls,test_met_session,test_met_cancel,test_met_list;
void xw_player_host_met_dispatch(uint32_t session,uint32_t cancel,uint32_t list){test_met_list=list;test_met_calls++;test_met_session=session;test_met_cancel=cancel;test_errno=99;}
#ifdef XW_PLAYER_NATIVE_PREPARE
#include "../../runtime/platform/player/host_managed_service.h"
unsigned test_exit_events,test_prepare_decisions;
void xw_player_host_note_native_exit(void){test_exit_events++;}
int xw_player_host_exit_decision(uint64_t epoch,void *context,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t)){
 (void)epoch;(void)context;(void)valid;(void)resume;test_prepare_decisions++;return XW_HOST_EXIT_FACTORY;
}
#endif
