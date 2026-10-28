#ifndef HB_QQMUSIC_SOURCE_H
#define HB_QQMUSIC_SOURCE_H
#include "qqmusic_stage.h"
#include "../../../sdk/include/x1000/services/volume.h"
struct qq_source_file {int fd,parent;uint64_t device,inode,parent_inode,bytes;char path[160];volatile int *stop;};
void qq_source_init(struct qq_source_file *);
/* Existing completed download in the same verified workspace. Hashes actual
 * bytes against completed transaction digest before granting codec read_at.
 * Caller holds exclusive workspace/source ownership until conversion ends. */
int qq_source_open(struct qq_source_file *,struct qq_volume *,const struct qq_storage_plan *,const struct qq_stage_file *,volatile int *);
/* Same read-only hash/identity checks for a READY encoded MP3 temporary. */
int qq_source_open_output(struct qq_source_file *,struct qq_volume *,const struct qq_storage_plan *,const struct qq_stage_file *,volatile int *);
int qq_source_read_at(void *,uint64_t,unsigned char *,unsigned);
int qq_source_close(struct qq_source_file *);
#endif
