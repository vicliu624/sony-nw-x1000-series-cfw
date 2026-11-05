#ifndef WR_RUN_PROFILE_H
#define WR_RUN_PROFILE_H
#include <stdint.h>
#include <stddef.h>
/* Trusted template after file/volume qualification. Success creates a RAM-only
 * run config; failure preserves output. Entropy must fill all requested bytes. */
int wr_run_profile(uint8_t[80],const uint8_t[80],uint64_t,void *,int (*)(void *,uint8_t *,size_t));
#endif
