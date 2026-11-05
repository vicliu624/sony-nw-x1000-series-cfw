#include "wireless_host.h"
#include "../wireless/native_publisher.h"
#include "../wireless/native_retirement.h"
#include "../wireless/native_delivery.h"
static struct xw_native_publisher publisher;
static struct xw_wireless_lease native_lease;
static int native_held,pending_native,stop_sent;
static uint64_t stopping_epoch;
static uint64_t handoff_epoch,handoff_serial,issued_epoch;
extern int xw_native_rf_stop_request(void);
int xw_player_host_wireless_player_active(void){return !stopping_epoch&&!handoff_epoch;}
int xw_player_host_wireless_next_epoch(uint64_t *output){
 if(!output)return XW_MODE_INVALID;
 if(stopping_epoch||!publisher.policy)return XW_MODE_DENIED;
 if(handoff_epoch)return XW_MODE_BUSY;
 struct xw_wireless_mode_snapshot state;
 int rc=xw_mode_policy_snapshot(publisher.policy,&state);if(rc)return rc;
 if(state.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 uint64_t previous=issued_epoch>handoff_serial?issued_epoch:handoff_serial;
 if(previous==UINT64_MAX)return XW_MODE_FAULT;
 issued_epoch=previous+1;*output=issued_epoch;return 0;
}
int xw_player_host_wireless_remote_mode(void){
 if(!publisher.policy)return XW_WIRELESS_MODE_UNKNOWN;
 int mode=xw_mode_policy_admitted(publisher.policy);
 return xw_player_host_wireless_player_active()?mode:XW_WIRELESS_MODE_UNKNOWN;
}
int xw_player_host_wireless_remote_acquire(struct xw_wireless_lease *lease){
 if(!lease)return XW_MODE_INVALID;
 if(!publisher.policy)return XW_MODE_DENIED;
 struct xw_wireless_mode_snapshot state;int rc=xw_mode_policy_snapshot(publisher.policy,&state);if(rc)return rc;
 if(!xw_player_host_wireless_player_active()||state.phase!=XW_MODE_STABLE||state.selected!=XW_WIRELESS_MODE_ESPNOW)return XW_MODE_DENIED;
 if(lease->generation||lease->serial||lease->consumer||lease->mode){
  if(!lease->generation||!lease->serial||lease->consumer!=XW_PLAYER_REMOTE_CONSUMER||lease->mode!=XW_WIRELESS_MODE_ESPNOW)return XW_MODE_INVALID;
  return xw_mode_policy_data_allowed(publisher.policy,lease);
 }
 return xw_mode_policy_acquire(publisher.policy,XW_WIRELESS_MODE_ESPNOW,XW_PLAYER_REMOTE_CONSUMER,lease);
}
int xw_player_host_wireless_remote_retired(const struct xw_wireless_lease *lease,int verified){
 if(!publisher.policy)return XW_MODE_DENIED;
 if(!lease||lease->consumer!=XW_PLAYER_REMOTE_CONSUMER||lease->mode!=XW_WIRELESS_MODE_ESPNOW)return XW_MODE_INVALID;
 return xw_mode_policy_release(publisher.policy,lease,verified);
}
int xw_player_host_wireless_remote_view(struct xw_mode_channel *view,int fd,const struct xw_wireless_lease *lease){
 if(!publisher.policy||!lease||lease->consumer!=XW_PLAYER_REMOTE_CONSUMER||lease->mode!=XW_WIRELESS_MODE_ESPNOW)return XW_MODE_DENIED;
 int rc=xw_mode_policy_data_allowed(publisher.policy,lease);if(rc)return rc;
 rc=xw_mode_channel_open(view,publisher.policy,fd,lease->consumer,XW_MODE_GRANT_READ);if(rc)return rc;
 rc=xw_mode_channel_observe(view,lease);
 if(rc)(void)xw_mode_channel_close(view);
 return rc;
}
int xw_native_rf_gui_cleanup_permission(void){
 if(!xw_native_rf_gui_owner()||!publisher.policy)return XW_MODE_DENIED;
 if(!native_held)return 2;
 return xw_mode_policy_owns(publisher.policy,&native_lease);
}
int xw_player_host_wireless_has_authority(void){return publisher.policy!=0;}
int xw_player_host_wireless_bound(struct xw_wireless_mode_policy *policy){
 int rc=xw_native_publisher_bind(&publisher,policy);if(rc)return rc;
 if(pending_native){
  pending_native=0;rc=xw_player_host_wireless_request(0x4c0007u);
  if(rc!=0&&rc!=XW_MODE_PENDING&&rc!=XW_MODE_DENIED)return rc;
 }
 return 0;
}
int xw_player_host_wireless_publish(const struct xw_wireless_lease *lease){
 return xw_native_publisher_prepare(&publisher,lease);
}
int xw_player_host_wireless_tick(void){
 if(!publisher.policy||!publisher.issued)return 0;
 if(native_held&&!stop_sent){
  struct xw_wireless_mode_snapshot state;int observed=xw_mode_policy_snapshot(publisher.policy,&state);if(observed)return observed;
  if(state.phase==XW_MODE_DRAINING){
   int stopping=xw_native_rf_stop_request();
   if(!stopping)stop_sent=1;
   else if(stopping!=XW_MODE_PENDING)(void)xw_mode_policy_release(publisher.policy,&native_lease,0);
  }
 }
 int rc=xw_native_publisher_step(&publisher);if(rc)return rc;
 /* Flush a just-constructed reply before any slower player dispatch. No
  * second idle poll, wait, file work or hardware action is added. */
 if(publisher.channel.pending){rc=xw_native_publisher_step(&publisher);if(rc)return rc;}
 struct xw_native_retirement receipt;rc=xw_native_rf_retirement_receive(&receipt);
 if(rc==XW_MODE_PENDING)return 0;if(rc)return rc;
 struct xw_wireless_mode_snapshot snapshot;rc=xw_mode_policy_snapshot(publisher.policy,&snapshot);if(rc)return rc;
 if(snapshot.phase!=XW_MODE_DRAINING&&snapshot.phase!=XW_MODE_FAILED)return 0;
 rc=xw_player_host_wireless_native_retired(&receipt.lease,receipt.native_result==0&&receipt.public_state==2&&receipt.modules_clear==1&&receipt.sealed==1);
 return rc==XW_MODE_STALE?0:rc;
}
int xw_player_host_wireless_backend_close(void){
 if(native_held)return XW_MODE_PENDING;
 if(publisher.policy){
  struct xw_wireless_mode_snapshot state;int rc=xw_mode_policy_snapshot(publisher.policy,&state);if(rc)return rc;
  if(state.active)return XW_MODE_PENDING;
 }
 return publisher.policy?xw_native_publisher_close(&publisher):0;
}
int xw_player_host_wireless_prepare_stop(uint64_t epoch){
 if(!epoch)return XW_MODE_INVALID;
 if(stopping_epoch&&stopping_epoch!=epoch)return XW_MODE_STALE;
 if(!publisher.policy)return XW_MODE_DENIED;
 struct xw_wireless_mode_snapshot state;int rc=xw_mode_policy_snapshot(publisher.policy,&state);if(rc)return rc;
 stopping_epoch=epoch;pending_native=0;
 if(state.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 if(state.active)return xw_mode_policy_quiesce(publisher.policy,&state.lease);
 return state.phase==XW_MODE_STABLE&&state.off_verified?0:XW_MODE_DENIED;
}
int xw_player_host_wireless_prepare_handoff(uint64_t epoch){
 if(!epoch)return XW_MODE_INVALID;
 if(stopping_epoch)return XW_MODE_DENIED;
 if(handoff_epoch&&handoff_epoch!=epoch)return XW_MODE_STALE;
 if(!handoff_epoch&&epoch<=handoff_serial)return XW_MODE_STALE;
 if(!publisher.policy)return XW_MODE_DENIED;
 struct xw_wireless_mode_snapshot state;int rc=xw_mode_policy_snapshot(publisher.policy,&state);if(rc)return rc;
 if(!handoff_epoch){
  handoff_epoch=handoff_serial=epoch;pending_native=0;
  if(state.active)return xw_mode_policy_quiesce(publisher.policy,&state.lease);
 }
 if(state.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 if(state.active||state.phase==XW_MODE_DRAINING)return XW_MODE_PENDING;
 return state.phase==XW_MODE_STABLE&&state.off_verified?0:XW_MODE_DENIED;
}
int xw_player_host_wireless_resume_handoff(uint64_t epoch){
 if(!epoch)return XW_MODE_INVALID;
 if(stopping_epoch)return XW_MODE_DENIED;
 if(!handoff_epoch||handoff_epoch!=epoch)return XW_MODE_STALE;
 struct xw_wireless_mode_snapshot state;int rc=xw_mode_policy_snapshot(publisher.policy,&state);if(rc)return rc;
 if(state.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 if(state.active||state.phase==XW_MODE_DRAINING)return XW_MODE_PENDING;
 if(state.phase!=XW_MODE_STABLE||!state.off_verified)return XW_MODE_DENIED;
 handoff_epoch=0;return 0;
}
int xw_player_host_wireless_request(uint32_t event){
 /* These requests can start scan/connect or WPS. Other configuration and
  * cleanup events still take the unmodified original router path. A WPS UI
  * event may also be configuration-only; reserving a lease never powers RF. */
 if(event!=0x4c0001u&&event!=0x4c0005u&&event!=0x4c0007u&&event!=0x4cc001u)return 0;
 if(stopping_epoch||handoff_epoch)return XW_MODE_DENIED;
 if(!publisher.policy){
  if(xw_player_host_wireless_initialization_status()!=XW_MODE_PENDING)return XW_MODE_DENIED;
  pending_native=1;return XW_MODE_PENDING;
 }
 struct xw_wireless_mode_snapshot snapshot;int rc=xw_mode_policy_snapshot(publisher.policy,&snapshot);if(rc)return rc;
 if(snapshot.phase!=XW_MODE_STABLE||snapshot.selected!=XW_WIRELESS_MODE_WIFI)return XW_MODE_DENIED;
 if(native_held){
  rc=xw_mode_policy_owns(publisher.policy,&native_lease);
  if(rc==XW_MODE_STALE)native_held=0;else if(rc)return rc;
 }
 if(!native_held){
  rc=xw_mode_policy_acquire(publisher.policy,XW_WIRELESS_MODE_WIFI,XW_NATIVE_WIFI_CONSUMER,&native_lease);
  if(rc)return rc;native_held=1;stop_sent=0;
 }
 return xw_player_host_wireless_publish(&native_lease);
}
int xw_player_host_wireless_native_retired(const struct xw_wireless_lease *lease,int verified){
 if(!publisher.policy||!native_held)return XW_MODE_STALE;
 if(!lease||lease->generation!=native_lease.generation||lease->serial!=native_lease.serial||
    lease->consumer!=native_lease.consumer||lease->mode!=native_lease.mode)return XW_MODE_STALE;
 int rc=xw_mode_policy_release(publisher.policy,&native_lease,verified);if(rc)return rc;
 native_held=0;stop_sent=0;return xw_native_publisher_retired(&publisher,lease);
}
