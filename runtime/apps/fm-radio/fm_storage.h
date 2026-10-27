#ifndef HB_FM_STORAGE_H
#define HB_FM_STORAGE_H
#include <stdint.h>
#include "fm_state.h"
enum fm_storage_result {FM_STORAGE_OK=0,FM_STORAGE_EMPTY=1,FM_STORAGE_IO=-1,FM_STORAGE_CORRUPT=-2,FM_STORAGE_BOUNDARY=-3,FM_STORAGE_SPACE=-4,FM_STORAGE_UNCERTAIN=-5};
struct fm_storage {int directory,slot;uint64_t device,inode;uint32_t generation;int (*validate)(void *);void *context;};
void fm_storage_init(struct fm_storage *);
/* Bind an already mount-verified directory. Checks that its actual device
 * differs from /, pins a duplicate descriptor and revalidates before IO.
 * Native callers use fm_storage_open(), not arbitrary application paths. */
int fm_storage_bind(struct fm_storage *,int,int (*)(void *),void *);
int fm_storage_load(struct fm_storage *,struct fm_band,struct fm_state *);
int fm_storage_save(struct fm_storage *,const struct fm_state *);
int fm_storage_close(struct fm_storage *);
/* Only /contents/HOMEBREW/data/fm-radio, matching stock vfat source. */
int fm_storage_open(struct fm_storage *);
int fm_storage_mounts_ok(const char *,unsigned);
#endif
