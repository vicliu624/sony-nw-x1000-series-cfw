#ifndef HB_QQMUSIC_PREVIEW_RECEIPT_H
#define HB_QQMUSIC_PREVIEW_RECEIPT_H
#include "qqmusic_preview_source_job.h"
#define QQ_PREVIEW_RECEIPT_BYTES 384u
struct qq_preview_receipt_store {const struct qq_job_config *config;};
/* Fresh UI-owned job/store, before launching its gated child. No IO. Refuses
 * to replace an already supplied receipt provider. */
int qq_preview_receipt_bind(struct qq_preview_source_job *,struct qq_preview_receipt_store *);
/* Durable retain callback: exact verified user workspace, exclusive new file,
 * no overwrite or system fallback. Source itself is never changed/deleted. */
int qq_preview_receipt_retain(void *,const struct qq_preview_source_receipt *,const struct qq_stage_file *);
/* Public, canonical versioned record only; no native struct/padding on disk. */
int qq_preview_receipt_encode(const struct qq_preview_source_receipt *,unsigned char *,size_t);
int qq_preview_receipt_decode(const unsigned char *,size_t,struct qq_preview_source_receipt *);
#endif
