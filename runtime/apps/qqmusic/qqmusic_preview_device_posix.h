#ifndef HB_QQMUSIC_PREVIEW_DEVICE_POSIX_H
#define HB_QQMUSIC_PREVIEW_DEVICE_POSIX_H
#include "qqmusic_preview_device.h"
#include "qqmusic_preview_handoff.h"
#include "qqmusic_workspace.h"
struct qq_preview_device_posix {
 const struct qq_preview_handoff_policy *policy;
 struct qq_workspace *workspace;
 volatile int *stop;unsigned role;
 void *producer_context;int (*producer_exited)(void *,uint64_t);
 struct qq_preview_handoff_receipt handoff;
 uint64_t generation;int retained_guard;unsigned parent,uncertain;
};
/* Fresh zeroed context with explicit inputs only; never rebind a live owner.
 * Populates real libc operations but performs no IO. No policy, verified
 * workspace, cancellation flag or real producer callback means refusal.
 * Caller must supervise process retirement/restore on abnormal worker death. */
int qq_preview_device_posix_io(struct qq_preview_device_posix *,struct qq_preview_device_io *);
#endif
