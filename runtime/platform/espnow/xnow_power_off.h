#ifndef XNOW_POWER_OFF_H
#define XNOW_POWER_OFF_H
#include "xnow_manager.h"
/* Optional final system-owner policy, after stock restoration and immediately
 * before RELEASE. Never called by ordinary SDK close. The callback returns1
 * only for a qualified exclusive original-radio/USB owner at this generation;
 * cnmgr reference count or an IPC path check alone does not qualify it.
 * Calls may block: run on the radio owner process, never the Sony UI thread.
 * Success verifies public cnmgr state2 and all four WLAN modules absent,
 * not measured rail voltage/current. Script success can hide partial unload.
 * Incomplete or unconfirmed unload retains manager uncertainty and its lease,
 * including a reported-off manager with residual WLAN modules.
 * Session fields are not advanced; caller still owns ordinary RELEASE/fin.
 */
int xnow_manager_power_off(struct xnow_manager *,const struct xnow_session *,
                           void *,int (*exclusive)(void *));
#endif
