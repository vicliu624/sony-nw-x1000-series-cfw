#ifndef XNOW_LOADER_JOB_H
#define XNOW_LOADER_JOB_H
#include "xnow_session.h"
/* Internal process adapter, not an installation command. Caller must verify
 * exact files/user mount/USB ownership before asking the session for a load.
 * Loads use the original script, with fixed paths and clean environment.
 * WAKE runs the stock ioctl adapter in a child, keeping blocking IO off the UI.
 */
struct xnow_loader_job { int pid,terminal,lost; enum xnow_session_action action; };
#ifdef __cplusplus
extern "C" {
#endif
void xnow_loader_job_init(struct xnow_loader_job *);
/* guard must freshly check mount/USB ownership and exact files for this action.
 * Missing or failed guard refuses to fork. Success is a snapshot, not a lock. */
int xnow_loader_job_start(struct xnow_loader_job *,const struct xnow_session *,
                         void *,int (*guard)(void *,enum xnow_session_action));
/* 1 still running, 0 drained (result filled), -1 invalid/lost child ownership.
 * Loader exit0 does NOT qualify the image: the session must VERIFY next.
 * No kill-on-timeout; abandoning an in-progress module init is unsafe.
 */
int xnow_loader_job_poll(struct xnow_loader_job *,int *result);
#ifdef __cplusplus
}
#endif
#endif
