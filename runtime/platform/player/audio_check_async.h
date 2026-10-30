/* Private per-intent audio preflight. No playback commands or native pointers. */
#ifndef XW_AUDIO_CHECK_ASYNC_H
#define XW_AUDIO_CHECK_ASYNC_H
#include "metadata_async.h"
struct xw_audio_check_async {struct xw_metadata_async worker;};
int xw_audio_check_async_init(struct xw_audio_check_async *);
/* GUI owner only. Use a new nonzero generation for each new intent, even for
 * the same ID. This is not a catalog revision. NULL revokes pending intent.
 * A successful result is a past observation, not a playback/existence lease.
 * Lifecycle: stop/drain/destroy worker using metadata_async functions. */
int xw_audio_check_async_observe(struct xw_audio_check_async *,const struct xw_media_id *,uint64_t request_generation,uint64_t now_ms,struct xw_stock_audio_identity *);
#endif
