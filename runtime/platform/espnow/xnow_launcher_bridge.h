#ifndef XNOW_LAUNCHER_BRIDGE_H
#define XNOW_LAUNCHER_BRIDGE_H
#include "../../native/app_catalog.h"
#include "../../native/app_process.h"
/* Experimental libc-launcher integration. Marker binds this opt-in contract
 * to the already verified app SHA; app.ini and old launcher paths unchanged.
 * No APF, RF or controller library is linked into the foreground bridge. */
#ifdef __cplusplus
extern "C" {
#endif
int xnow_launcher_managed_mode(const struct hb_app *); /*0 legacy,1 managed,-1 bad */
/* Blocks through UI reap and explicit owner handoff. Uncertain cleanup keeps
 * foreground alive; never returns merely because owner EOF/crash occurred.
 * Caller/device manager can still kill it; real APF deadlines unqualified. */
int xnow_launcher_run_managed(const char *,const char *,char *const [],volatile int *,const struct hb_process_observer *);
#ifdef __cplusplus
}
#endif
#endif
