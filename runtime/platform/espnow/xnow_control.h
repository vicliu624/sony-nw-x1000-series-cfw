#ifndef XNOW_CONTROL_H
#define XNOW_CONTROL_H
#include "xnow_session.h"
#include "xnow_manager.h"
#include "xnow_loader_job.h"
#include "xnow_sd8686.h"
/* One serialized OWNER process; manager calls and some ioctls may block. Never
 * use step() on a UI thread or from signal handlers. No deployment/default guard.
 * init() is for a fresh object only; do not reset an active/uncertain owner.
 */
struct xnow_control_options {
    void *context;
    int (*radio_guard)(void *,enum xnow_session_action);
    int (*ipc_guard)(void *,enum xnow_session_action);
    unsigned channel,allow_disconnect;
};
struct xnow_control {
    struct xnow_control_options options;
    struct xnow_session session;
    struct xnow_manager manager;
    struct xnow_loader_job job;
    struct xnow_sd8686 radio;
    struct xnow_mailbox mailbox;
    int initialized,stepping,uncertain,stock_rehearsal;
};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_control_init(struct xnow_control *,const struct xnow_control_options *);
/* Explicit diagnostic: acquire/capture/disconnect, then the unchanged stock
 * restoration chain once. Never loads a candidate, exposes a mailbox or sets
 * a channel. Same mandatory guards, worker ownership and repair policy apply.
 * DONE is success only if failure and restore_failure are both zero. */
int xnow_control_init_stock_rehearsal(struct xnow_control *,const struct xnow_control_options *);
/* Returns session phase, or a negative error/uncertainty. DONE means quiescent;
 * inspect session.failure for startup errors. Never conflate it with success.
 * Each step completes at most one action; in-flight children must drain first.
 */
int xnow_control_step(struct xnow_control *);
void xnow_control_stop(struct xnow_control *);
int xnow_control_retry_restore(struct xnow_control *);
/* A retained pointer becomes unusable as soon as stop closes its radio adapter. */
struct xnow_mailbox *xnow_control_mailbox(struct xnow_control *);
int xnow_control_finished(const struct xnow_control *);
#ifdef __cplusplus
}
#endif
#endif
