#ifndef HB_QQMUSIC_PREVIEW_SOURCE_JOB_H
#define HB_QQMUSIC_PREVIEW_SOURCE_JOB_H
#include "qqmusic_preview_client.h"
#include "qqmusic_job.h"
#include "qqmusic_stage.h"
/* Public completed-source evidence only; no signed URL, ekey or account state. */
struct qq_preview_source_receipt {
 char identity[65],nonce[17],song_mid[65],media_mid[65],filename[81];
 uint64_t bytes;unsigned char sha256[32];
};
struct qq_preview_source_job {
 const struct qq_job_config *config;const struct qq_worker_request *request;
 void *receipt_context;
 /* Mandatory durable user-volume receipt before decoding. Completed originals
  * are retained on every path, including callback failure/cancellation. */
 int (*retain)(void *,const struct qq_preview_source_receipt *,const struct qq_stage_file *);
};
/* qq_preview_worker_entry: runs only behind the acknowledged start gate.
 * Fresh network/source state, verified user workspace, new authorized download,
 * protected reader and limited decoder. Never opens MUSIC or publishes MP3. */
int qq_preview_source_job_run(void *,const struct qq_preview_worker_job *);
#endif
