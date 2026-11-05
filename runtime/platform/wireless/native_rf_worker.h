#ifndef XW_NATIVE_RF_WORKER_H
#define XW_NATIVE_RF_WORKER_H
#include "mode_policy.h"
#define XW_NATIVE_RF_CLEANUP_VIEW 2
/* Trusted provisioning on the native worker only. The descriptor must be its
 * READ-only view of the supplied existing lease, never a caller-created right. */
int xw_native_rf_worker_bind(int,int,unsigned long,const struct xw_wireless_lease *);
/* Same-worker renewal: accept only a fresh capability for a strictly newer
 * serial at the same authority/consumer. Validate it before replacing TLS. */
int xw_native_rf_worker_replace(int,int,unsigned long,const struct xw_wireless_lease *);
/* Trusted received capability: initial bind is validated before returning;
 * existing TLS is replaced only after fresh-capability validation succeeds. */
int xw_native_rf_worker_offer(int,int,unsigned long,const struct xw_wireless_lease *);
int xw_native_rf_worker_close(void);
int xw_native_rf_permission(void);
struct xw_mode_reply;
int xw_native_rf_worker_observe(struct xw_mode_reply *);
struct xw_native_retirement;
int xw_native_rf_worker_seal(const struct xw_native_retirement *);
int xw_native_rf_worker_retirement(struct xw_native_retirement *);
int xw_native_rf_worker_notice_pending(void);
void xw_native_rf_worker_notice_sent(const struct xw_wireless_lease *);
/*0 permits the current native cleanup,2 is an already-retired native no-op. */
int xw_native_rf_cleanup_permission(void);
#endif
