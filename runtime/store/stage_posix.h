#ifndef HB_STORE_STAGE_POSIX_H
#define HB_STORE_STAGE_POSIX_H
#include "bundle_posix.h"
enum hb_stage_result {
 HB_STAGE_OK=0,HB_STAGE_INVALID=-20,HB_STAGE_IO=-21,HB_STAGE_NO_SPACE=-22,
 HB_STAGE_CANCELLED=-23,HB_STAGE_SIZE=-24,HB_STAGE_HASH=-25,
 HB_STAGE_EXISTS=-26,HB_STAGE_VERIFY=-27
};
/* Creates only <parent>/.install-<id>, never activates or removes LIVE/BACKUP.
 * Existing stage is refused. On failure a partial inactive stage may remain.
 * All paths must be canonical; package must not overlap the parent tree.
 * Caller supplies workspace and keeps source/parent unchanged during the call. */
int hb_bundle_stage(const char *source,const char *id,const char *parent,
                    unsigned long long reserve,volatile int *stop,struct hb_bundle *workspace);
#endif
