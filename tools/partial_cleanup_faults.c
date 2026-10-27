/* Test-only composition: existing I/O fault wrappers plus real process exit. */
#define __wrap_fsync hb_partial_regular_fsync
#include "download_file_faults.c"
#undef __wrap_fsync
static unsigned exit_target,exit_seen;
void hb_partial_exit_at(unsigned target){exit_target=target;exit_seen=0;}
int __wrap_fsync(int fd){if(exit_target&&++exit_seen==exit_target)_exit(77);return hb_partial_regular_fsync(fd);}
