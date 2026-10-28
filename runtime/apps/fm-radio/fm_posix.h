#ifndef HB_FM_POSIX_H
#define HB_FM_POSIX_H
#include "../../../sdk/include/x1000/services/fm_session.h"
struct fm_posix {int mixer,tuner;volatile int *stop;};
/* Build-only native adapter. Its caller must already have Sony's resources;
 * these device opens do not establish exclusive audio or lifecycle ownership. */
struct fm_session_ops fm_posix_ops(struct fm_posix *,volatile int *);
int fm_os_open(const char *,int);
int fm_os_close(int);
int fm_os_ioctl(int,unsigned long,void *);
int fm_os_usleep(unsigned);
#endif
