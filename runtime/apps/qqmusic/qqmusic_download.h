#ifndef HB_QQMUSIC_DOWNLOAD_H
#define HB_QQMUSIC_DOWNLOAD_H
#include "qqmusic_stage.h"
#include "qqmusic_volume.h"
struct qq_download_file {struct qq_stage_file stage;struct qq_volume *volume;struct qq_storage_plan plan;};
void qq_download_init(struct qq_download_file *);
int qq_download_begin(struct qq_download_file *,struct qq_volume *,const struct qq_storage_plan *,const char *identity64,const char *nonce16,uint64_t maximum,volatile int *);
struct qq_response_sink qq_download_sink(struct qq_download_file *);
/* Cancellation removes only incomplete owned download. READY is retained and
 * must be taken by caller, including on application stop, never silently lost. */
int qq_download_abort(struct qq_download_file *);
/* Move completed source transaction ownership into initialized EMPTY object. */
int qq_download_take(struct qq_download_file *,struct qq_stage_file *);
#endif
