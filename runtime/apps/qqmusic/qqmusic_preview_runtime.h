#ifndef HB_QQMUSIC_PREVIEW_RUNTIME_H
#define HB_QQMUSIC_PREVIEW_RUNTIME_H
#include "qqmusic_preview_handoff.h"
#include "qqmusic_preview_supervisor.h"
#include "qqmusic_workspace.h"
/* Root entry before account initialization. UI callback runs only in its child
 * with inherited verified workspace and private cancellation flag. Root owns
 * actual audio service, reviewed POSIX binding and process supervision. */
int qq_preview_runtime_run(const struct qq_preview_handoff_policy *,struct qq_workspace *,volatile int *,
 int (*ui)(void *,const struct qq_preview_client_channels *,volatile int *),void *ui_context);
#endif
