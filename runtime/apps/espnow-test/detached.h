#ifndef ESPNOW_TEST_DETACHED_H
#define ESPNOW_TEST_DETACHED_H
/* Caller supplies a new, validated user-volume journal FD and its path.
 * Parent closes its copy; child owns it through run(). No filesystem fallback. */
int probe_detach(int journal_fd,const char *path,int (*run)(int));
#endif
