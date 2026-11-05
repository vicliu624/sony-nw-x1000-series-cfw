#ifndef XW_NATIVE_WIRELESS_PERMISSION_H
#define XW_NATIVE_WIRELESS_PERMISSION_H
#include "mode_client.h"
#include "native_retirement.h"
struct xw_native_wireless_permission {
 struct xw_mode_client client;struct xw_wireless_lease lease;
 int gui_pid,fault;unsigned long gui_thread;
 int sealed,retirement_sent;struct xw_native_retirement retirement;
};
#ifdef __cplusplus
extern "C" {
#endif
/* Bind on the actual native worker, with trusted GUI identity and the exact
 * native lease whose READ-only channel is supplied. No thread is created. */
int xw_native_permission_open(struct xw_native_wireless_permission *,int fd,int gui_pid,unsigned long gui_thread,const struct xw_wireless_lease *);
/* Worker-only synchronous boundary for a stock synchronous RF call. At most
 *200ms, never callable by the GUI owner. Timeout closes only the observation
 * channel and denies work; it cannot release ownership or declare radio off. */
int xw_native_permission_check(struct xw_native_wireless_permission *,unsigned timeout_ms);
/* Fresh exact-lease observation for original cleanup. Ownership survives drain;
 * this observation never grants data admission. Output is unchanged on failure. */
int xw_native_permission_snapshot(struct xw_native_wireless_permission *,unsigned timeout_ms,struct xw_mode_reply *);
int xw_native_permission_close(struct xw_native_wireless_permission *);
#ifdef __cplusplus
}
#endif
#endif
