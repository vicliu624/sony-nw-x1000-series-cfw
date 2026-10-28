#ifndef HB_QQMUSIC_PREVIEW_OWNERS_H
#define HB_QQMUSIC_PREVIEW_OWNERS_H
#include <stdint.h>
/* Read-only global FD scan by regular-file identity, including orphaned workers.
 * Root is excluded. A UI exclusion requires its current PID and birth identity.
 * 1 quiet, 0 another holder/process race, -1 unknown or invalid guard.
 * Caller must prevent creation of new workers before using a quiet result. */
int qq_preview_guard_quiet(int guard_fd,unsigned ui_pid,uint64_t ui_birth);
/* 1 stable current identity,0 gone,-1 unknown. */
int qq_preview_process_identity(unsigned pid,unsigned *parent,uint64_t *birth);
int qq_preview_process_status(unsigned pid,unsigned *parent,uint64_t *birth,char *state);
#endif
