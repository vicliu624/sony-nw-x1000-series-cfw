#ifndef HB_QQMUSIC_PUBLISH_H
#define HB_QQMUSIC_PUBLISH_H
#include "qqmusic_directory.h"
#include "qqmusic_output.h"
#include "qqmusic_mp3.h"
enum qq_publish_result {QQ_PUBLISH_OK=0,QQ_PUBLISH_ERROR=-1,QQ_PUBLISH_CONFLICT=-2,QQ_PUBLISH_BUSY=-3,QQ_PUBLISH_REVIEW=-4};
struct qq_publish_report {char path[2049];uint64_t bytes;unsigned char digest[32];};
/* Exclusive app-owned artist/album namespace, no other writers (including USB)
 * until return. Per-album mkdir lock serializes cooperating publishers; this
 * old-kernel rename is NOT atomic no-replace against arbitrary outside writers.
 * Existing destination always rejects. Before rename failure retains temporary;
 * after rename uncertainty retains final and lock for explicit recovery. No DB
 * refresh or source download removal. Caller must not auto-abort REVIEW files. */
int qq_publish_mp3(struct qq_output_file *,struct qq_export_directory *,const struct qq_storage_plan *,const struct qq_import_report *,struct qq_publish_report *);
#endif
