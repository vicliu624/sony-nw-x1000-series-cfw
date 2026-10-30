#ifndef GM_APP_HANDOFF_H
#define GM_APP_HANDOFF_H
#include <stdint.h>
struct gm_handoff {int fd;uint8_t cookie[16];uint64_t device,inode;};
int gm_handoff_adopt(struct gm_handoff *);
int gm_handoff_startup_failed(struct gm_handoff *);
/* Owner-private record writer; not a public SDK proof of restoration. */
int gm_handoff_write(struct gm_handoff *,unsigned failure);
#endif
