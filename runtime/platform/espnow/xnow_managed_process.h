#ifndef XNOW_MANAGED_PROCESS_H
#define XNOW_MANAGED_PROCESS_H
#include "xnow_handoff.h"
#include "../../native/app_process.h"
/* Experimental SDK opt-in wrapper, not the production launcher's default.
 * begin runs/waits UI exactly through existing app_process; after UI reap,
 * poll/close retain foreground dependency until managed owner DONE+EOF.
 * On uncertainty caller must stay in repair state, not return to Sony/APF.
 * Original callback, grace and ordinary app entry points stay unchanged. */
struct xnow_managed_process {struct xnow_handoff handoff;int app_status,started,complete,fault;};
#ifdef __cplusplus
extern "C" {
#endif
/* Fresh object; bounded env copy. Existing reserved handoff variables refused.
 * Cookie must be fresh launch correlation, not an authentication credential. */
int xnow_managed_process_begin(struct xnow_managed_process *,const char *,const char *,char *const [],volatile int *,const struct hb_process_observer *,const uint8_t cookie[16]);
int xnow_managed_process_poll(struct xnow_managed_process *,struct xnow_handoff_result *);
int xnow_managed_process_close(struct xnow_managed_process *);
/* Explicit app-side adoption of inherited capability; no radio operation.
 * Reinstates CLOEXEC: verified owner transfer must deliberately clear it again. */
int xnow_managed_process_inherited(int *writer,uint8_t cookie[16]);
#ifdef __cplusplus
}
#endif
#endif
