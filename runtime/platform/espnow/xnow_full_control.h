#ifndef XNOW_FULL_CONTROL_H
#define XNOW_FULL_CONTROL_H
#include "xnow_control.h"
#include "xnow_sd8686_full.h"
#include "xnow_endpoint.h"
/* Experimental full owner, one serialized controller process. Uses original
 * manager/loader/session actions. Guards must supply actual exclusive radio,
 * image identity, user-volume/USB and epoch ownership; no permissive default.
 * Current loader's candidate directory remains the original user-data path.
 * Fresh object only; never reset an active/uncertain controller. */
struct xnow_full_control_options {
 void *context;const struct xnow_full_profile *profile;
 int (*radio_guard)(void *,enum xnow_session_action);
 int (*ipc_guard)(void *,enum xnow_session_action);
 int (*lease_valid)(void *);
 int (*random)(void *,uint8_t[4]);
 unsigned channel,allow_disconnect,encrypted_limit;
};
struct xnow_full_control {
 struct xnow_full_control_options options;struct xnow_session session;
 struct xnow_manager manager;struct xnow_loader_job job;
 struct xnow_sd8686_full radio;struct xnow_word_io bounded;
 struct xnow_full backend;struct xnow_endpoint endpoint;uint8_t local_mac[6];
 int initialized,stepping,uncertain,stop_requested,endpoint_ready;
};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_full_control_init(struct xnow_full_control *,const struct xnow_full_control_options *);
/* One action/worker poll per step. While drain is pending phase stays READY,
 * but endpoint accessor refuses new work. Blocking stock calls stay off UI. */
int xnow_full_control_step(struct xnow_full_control *);
void xnow_full_control_stop(struct xnow_full_control *);
int xnow_full_control_retry_restore(struct xnow_full_control *);
struct xnow_endpoint *xnow_full_control_endpoint(struct xnow_full_control *);
int xnow_full_control_finished(const struct xnow_full_control *);
#ifdef __cplusplus
}
#endif
#endif
