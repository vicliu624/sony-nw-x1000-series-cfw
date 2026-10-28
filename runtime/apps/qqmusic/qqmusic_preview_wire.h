#ifndef HB_QQMUSIC_PREVIEW_WIRE_H
#define HB_QQMUSIC_PREVIEW_WIRE_H
#include <stdint.h>
#include <stddef.h>
#define QQ_PREVIEW_RECORD_BYTES 32u
#define QQ_PREVIEW_PCM_BYTES 4064u
enum qq_preview_record_type {
 QQ_PREVIEW_BEGIN=1,QQ_PREVIEW_BIND=2,QQ_PREVIEW_FORMAT=3,
 QQ_PREVIEW_STOP=4,QQ_PREVIEW_REAPED=5,QQ_PREVIEW_PCM=6,
 QQ_PREVIEW_END=7,QQ_PREVIEW_STATUS=128
};
struct qq_preview_record {
 uint64_t generation,value;uint32_t sequence,argument;unsigned type;
};
/* Fixed little-endian numeric records only: no paths, URLs, credentials or
 * arbitrary payload commands. PCM record+payload fits4096-byte PIPE_BUF.
 * Caller separately verifies BIND process ownership and semantic phase. */
int qq_preview_record_encode(const struct qq_preview_record *,unsigned char *,size_t);
int qq_preview_record_decode(const unsigned char *,size_t,uint64_t expected_generation,
 uint32_t expected_sequence,struct qq_preview_record *);
#endif
