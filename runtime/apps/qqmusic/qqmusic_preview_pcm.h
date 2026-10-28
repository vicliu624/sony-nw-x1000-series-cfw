#ifndef HB_QQMUSIC_PREVIEW_PCM_H
#define HB_QQMUSIC_PREVIEW_PCM_H
#include "qqmusic_preview_decode.h"
/* Streaming preview-only PCM adaptation for the verified OSS negotiation:
 * PCM16LE stereo44100. Linear interpolation, bounded4096-byte staging;
 * ordinary44100 stereo stays byte-identical, mono is duplicated, no file IO.
 * Source is already limited by qq_preview_decode to at most30 seconds. */
struct qq_preview_pcm {
 struct qq_preview_sink output;
 volatile int *stop;
 uint64_t received,produced,position;
 unsigned rate,channels,used,configured,finished,failed;
 int older[2],previous[2],current[2];unsigned char bytes[4096];
};
int qq_preview_pcm_init(struct qq_preview_pcm *,const struct qq_preview_sink *,volatile int *stop);
struct qq_preview_sink qq_preview_pcm_sink(struct qq_preview_pcm *);
/* Successful decoder EOF/prefix only. Extends the last sample for the final
 * fractional interval, flushes all pending bytes once. Never call on cancel. */
int qq_preview_pcm_finish(struct qq_preview_pcm *);
void qq_preview_pcm_clear(struct qq_preview_pcm *);
#endif
