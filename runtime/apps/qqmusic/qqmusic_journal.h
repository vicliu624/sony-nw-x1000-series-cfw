#ifndef HB_QQMUSIC_JOURNAL_H
#define HB_QQMUSIC_JOURNAL_H
#include "qqmusic_job_record.h"
#include "qqmusic_volume.h"
#define QQ_JOURNAL_MAX_BYTES 131072u
struct qq_journal {
 int fd,parent,failed;struct qq_volume *volume;struct qq_storage_plan plan;
 uint64_t inode,bytes;unsigned sequence;enum qq_job_event event;
 char name[128],path[160];unsigned char digest[32];struct qq_job_record last;
};
struct qq_journal_snapshot {unsigned records;enum qq_job_event event;struct qq_job_record last;};
enum qq_journal_result {QQ_JOURNAL_OK,QQ_JOURNAL_REVIEW,QQ_JOURNAL_INVALID=-1};
void qq_journal_init(struct qq_journal *);
/* Exclusive fixed-name create on BEGIN; append only, eight records maximum.
 * Explicit LE/version/length/sequence/chained SHA256, no C struct serialization.
 * Any IO failure poisons writer; never truncate, overwrite, unlink or retry an
 * ambiguous append. All failures retain evidence for read-only recovery. */
int qq_journal_append(struct qq_journal *,struct qq_volume *,const struct qq_storage_plan *,enum qq_job_event,const struct qq_job_record *);
int qq_journal_close(struct qq_journal *);
/* Reads known journal basename below verified workspace, no file actions.
 * REVIEW reports only the complete verified prefix. Caller must never infer
 * success from a terminal prefix when result != OK. No automatic recovery. */
int qq_journal_read(struct qq_volume *,const struct qq_storage_plan *,const char *name,struct qq_journal_snapshot *);
/* Bounded read-only catalog: at most4096 entries and limit1..128 journals.
 * Callback copies borrowed name/snapshot if needed; 0 continue,1 stop,-1 fail.
 * REVIEW can also indicate a partial catalog. No deleting or repairing files. */
int qq_journal_scan(struct qq_volume *,const struct qq_storage_plan *,unsigned limit,
 int (*visit)(void *,const char *,int,const struct qq_journal_snapshot *),void *,unsigned *count);
#endif
