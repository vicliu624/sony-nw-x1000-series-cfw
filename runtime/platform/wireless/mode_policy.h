#ifndef XW_WIRELESS_MODE_POLICY_H
#define XW_WIRELESS_MODE_POLICY_H
#include "mode.h"
#include <stdint.h>
/* Private serialized system-owner core, not a cross-process server or hardware
 * detector. Trusted adapters supply fresh generations, consumer identities and
 * actual native/off evidence. Never instantiate an app-local copy as a global
 * lock. No player, radio loader, NVP, persistence, threads or timer is owned. */
enum {XW_MODE_OK=0,XW_MODE_PENDING=1,XW_MODE_INVALID=-1,XW_MODE_STALE=-2,
      XW_MODE_DENIED=-3,XW_MODE_FAULT=-4,XW_MODE_BUSY=-5,XW_MODE_WRONG_OWNER=-6};
enum {XW_MODE_UNVERIFIED=1,XW_MODE_STABLE,XW_MODE_DRAINING,XW_MODE_FAILED};
struct xw_wireless_lease {uint64_t generation,serial,consumer;int mode;};
struct xw_wireless_mode_snapshot {
 int selected,requested;unsigned phase,active,off_verified;
 struct xw_wireless_lease lease;
};
struct xw_wireless_mode_policy {
 int owner_pid;unsigned long owner_thread;uint64_t generation,serial;
 struct xw_wireless_mode_snapshot state;
};
#ifdef __cplusplus
extern "C" {
#endif
int xw_mode_policy_init(struct xw_wireless_mode_policy *,uint64_t generation);
/* Explicit bootstrap/repair only: no active lease, verified original radio off.
 * Selection alone never powers a radio. No timeout invents this evidence. */
int xw_mode_policy_confirm_off(struct xw_wireless_mode_policy *,int mode,int verified);
/* Bootstrap representation of a qualified preexisting stock Wi-Fi owner. */
int xw_mode_policy_adopt_wifi(struct xw_wireless_mode_policy *,uint64_t consumer,int verified,struct xw_wireless_lease *);
/* Privileged system setting, not a consumer method. While DRAINING the old
 * owner stays owned, data admission stops and no new mode can acquire. */
int xw_mode_policy_request(struct xw_wireless_mode_policy *,int mode);
int xw_mode_policy_admitted(struct xw_wireless_mode_policy *);
int xw_mode_policy_snapshot(struct xw_wireless_mode_policy *,struct xw_wireless_mode_snapshot *);
int xw_mode_policy_acquire(struct xw_wireless_mode_policy *,int mode,uint64_t consumer,struct xw_wireless_lease *);
/* Ownership survives drain/fault for restoration; permission to send data does
 * not. Evidence is supplied only by the trusted original resource adapter. */
int xw_mode_policy_owns(struct xw_wireless_mode_policy *,const struct xw_wireless_lease *);
int xw_mode_policy_data_allowed(struct xw_wireless_mode_policy *,const struct xw_wireless_lease *);
/* Consumer close intent: revoke data/admission but retain ownership for drain.
 * Does not replace an already pending administrator-selected target mode. */
int xw_mode_policy_quiesce(struct xw_wireless_mode_policy *,const struct xw_wireless_lease *);
int xw_mode_policy_release(struct xw_wireless_mode_policy *,const struct xw_wireless_lease *,int off_verified);
#ifdef __cplusplus
}
#endif
#endif
