#ifndef XNOW_HANDOFF_H
#define XNOW_HANDOFF_H
#include "xnow_mailbox.h"
struct xnow_full_control;
/* Experimental SDK: foreground supervisor must remain alive while poll is
 * pending/uncertain. This pipe does not itself stop APF or prove USB ownership.
 * Cookie correlates one launch, not cryptographic peer/process authentication.
 * Owner closes all user-storage FDs/cwd before notify, then closes writer.
 * No signal handlers, timeout kills, manager messages or device I/O here. */
struct xnow_handoff {int reader,writer,pid,armed,done,fault;uint64_t device,inode;unsigned used;uint8_t cookie[16],record[33];};
struct xnow_handoff_result {int startup_failure;};
#ifdef __cplusplus
extern "C" {
#endif
/* Fresh object only; never reset an armed/pending object to bypass failure. */
int xnow_handoff_create(struct xnow_handoff *,const uint8_t cookie[16]);
/* Called only in app-launch child before exec; returns inheritable writer FD. */
int xnow_handoff_child_inherit(struct xnow_handoff *);
/* Called by supervisor after fork; drops only its own writer copy. */
int xnow_handoff_parent_arm(struct xnow_handoff *);
int xnow_handoff_poll(struct xnow_handoff *,struct xnow_handoff_result *);
int xnow_handoff_notify(int writer,const uint8_t cookie[16],const struct xnow_full_control *);
/* Refuses armed pending/uncertain handoff; caller must not treat EOF as DONE. */
int xnow_handoff_close(struct xnow_handoff *);
#ifdef __cplusplus
}
#endif
#endif
