#ifndef XW_WIRELESS_NATIVE_OWNER_H
#define XW_WIRELESS_NATIVE_OWNER_H
#include "mode_policy.h"
/* Authority-thread adapter for a qualified stock queue. It owns one native
 * radio lease, not one lease per queued message. Original cleanup/cancel and
 * pointer lifetimes remain the native adapter's responsibility. */
struct xw_native_wireless_owner {
 struct xw_wireless_mode_policy *policy;struct xw_wireless_lease lease;
 void *context;
 int (*enqueue)(void *,const uint32_t message[4]);
 int (*stop)(void *,const struct xw_wireless_lease *);
 int (*retirement)(void *,const struct xw_wireless_lease *);
 uint64_t consumer;int held,stopping,fault;
};
#ifdef __cplusplus
extern "C" {
#endif
int xw_native_wireless_bind(struct xw_native_wireless_owner *,struct xw_wireless_mode_policy *,uint64_t consumer,void *,int (*enqueue)(void *,const uint32_t[4]),int (*stop)(void *,const struct xw_wireless_lease *),int (*retirement)(void *,const struct xw_wireless_lease *));
/* Call only for already-classified stock RF work. No event pointer is retained.
 * enqueue must copy the native16-byte message synchronously and return0. */
int xw_native_wireless_submit(struct xw_native_wireless_owner *,const uint32_t message[4]);
/* Adopt only an existing authority-issued native lease after qualified stock
 * bootstrap. This is not permission to infer ownership from cnmgr state. */
int xw_native_wireless_adopt(struct xw_native_wireless_owner *,const struct xw_wireless_lease *);
/* Native natural shutdown or a mode change begins cooperative retirement.
 * stop returns0 only if the native stop request was accepted; retirement
 * returns1 while pending,0 only after qualified off, negative on uncertainty. */
int xw_native_wireless_stop(struct xw_native_wireless_owner *);
int xw_native_wireless_poll(struct xw_native_wireless_owner *);
#ifdef __cplusplus
}
#endif
#endif
