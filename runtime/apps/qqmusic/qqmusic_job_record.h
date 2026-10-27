#ifndef HB_QQMUSIC_JOB_RECORD_H
#define HB_QQMUSIC_JOB_RECORD_H
#include <stdint.h>
enum qq_job_event {QQ_JOB_BEGIN,QQ_JOB_SOURCE_READY,QQ_JOB_OUTPUT_READY,QQ_JOB_PUBLISHING,QQ_JOB_PUBLISHED,QQ_JOB_FAILED,QQ_JOB_CANCELLED,QQ_JOB_REVIEW};
/* No authentication material; explicit public IDs and retained file evidence. */
struct qq_job_record {unsigned version,source_quality,song_type,bitrate_kbps;char identity[65],nonce[17],song_mid[65],media_mid[65],filename[81],source[2049],temporary[2049],final[2049];uint64_t source_bytes,mp3_bytes;unsigned char source_sha256[32],mp3_sha256[32];};
#endif
