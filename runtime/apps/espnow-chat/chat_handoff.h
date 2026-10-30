#ifndef CHAT_HANDOFF_H
#define CHAT_HANDOFF_H
#include <stdint.h>
struct xnow_control;
struct chat_handoff {int fd;uint8_t cookie[16];uint64_t device,inode;};
int chat_handoff_adopt(struct chat_handoff *);
int chat_handoff_startup_failed(struct chat_handoff *);
/* Owner-private record writer; not a public SDK proof of restoration. */
int chat_handoff_write(struct chat_handoff *,unsigned failure);
/* Requires the legacy controller's completed restoration. Caller closes
 * user-storage descriptors and leaves user cwd first. Startup failure uses
 * startup_failed(), only before any radio action was started. */
int chat_handoff_finish(struct chat_handoff *,const struct xnow_control *,unsigned failure);
#endif
