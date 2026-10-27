#ifndef QQMUSIC_WORKSPACE_H
#define QQMUSIC_WORKSPACE_H
#include "qqmusic_volume.h"
/* One app instance owns this workspace. USB must be disconnected during native
 * use; this is not a USB driver lock or a guarantee against external raw IO. */
struct qq_workspace {struct qq_volume volume;int lock;uint64_t inode;volatile int *stop;};
void qq_workspace_init(struct qq_workspace *);
int qq_workspace_open(struct qq_workspace *,const struct qq_storage_policy *,volatile int *);
int qq_workspace_check(void *);
int qq_workspace_close(struct qq_workspace *);
#endif
