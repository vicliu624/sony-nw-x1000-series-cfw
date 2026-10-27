#ifndef QQMUSIC_INSTALLATION_H
#define QQMUSIC_INSTALLATION_H
#include <stddef.h>
#include <stdint.h>
/* Pinned verified user directory. Generates once, never rotates after a service
 * rejection. No account data; caller owns the workspace's exclusive lease. */
int qq_installation_material(int,uint64_t,const char *,const char *,char *,size_t,char *,size_t,char[33],volatile int *);
#endif
