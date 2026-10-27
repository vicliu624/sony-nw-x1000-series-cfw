/* Test-only composition: payload-cache faults plus exit at cleanup fsync. */
#define __wrap_fsync hb_recovery_normal_fsync
#include "payload_cache_faults.c"
#undef __wrap_fsync
static unsigned exit_fsync_target,exit_fsync_seen;
void hb_recovery_exit_at(unsigned target){exit_fsync_target=target;exit_fsync_seen=0;}
int __wrap_fsync(int fd){if(exit_fsync_target&&++exit_fsync_seen==exit_fsync_target)_exit(77);return hb_recovery_normal_fsync(fd);}
