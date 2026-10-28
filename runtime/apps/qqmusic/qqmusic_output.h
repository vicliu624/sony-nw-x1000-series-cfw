#ifndef HB_QQMUSIC_OUTPUT_H
#define HB_QQMUSIC_OUTPUT_H
#include "qqmusic_stage.h"
#include "../../../sdk/include/x1000/services/volume.h"
struct qq_output_file {struct qq_stage_file stage;struct qq_volume *volume;struct qq_storage_plan plan;};
void qq_output_init(struct qq_output_file *);
/* Verified existing workspace only. Plan must budget maximum MP3 bytes and at
 * least one MP3 file. No final path, overwrite, source mutation or publication. */
int qq_output_begin(struct qq_output_file *,struct qq_volume *,const struct qq_storage_plan *,const char *identity64,const char *nonce16,uint64_t maximum,volatile int *);
/* Suitable for qq_codec_io.write. Failure aborts only this owned output. */
int qq_output_write(void *,const unsigned char *,unsigned);
int qq_output_finish(struct qq_output_file *,uint64_t expected_bytes);
int qq_output_abort(struct qq_output_file *);
#endif
