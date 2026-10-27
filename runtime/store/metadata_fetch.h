#ifndef HB_STORE_METADATA_FETCH_H
#define HB_STORE_METADATA_FETCH_H
#include "download_task.h"
#include "metadata_cache.h"
#define HB_METADATA_BYTES HB_METADATA_CACHE_BYTES
enum hb_metadata_state {HB_METADATA_EMPTY,HB_METADATA_FETCHING,HB_METADATA_READY,HB_METADATA_FAILED,HB_METADATA_RECOVERY};
struct hb_metadata_fetch {struct hb_download_task task;struct hb_metadata_cache previous;int used_cache;unsigned char data[HB_METADATA_BYTES];unsigned bytes;int error;enum hb_metadata_state state;};
/* Known expected size/hash supplied by trusted repository configuration or a
 * verified catalog entry, not inferred from the downloaded response itself.
 * Anchors/options/stop lifetimes follow download_task. No device access here. */
void hb_metadata_fetch_init(struct hb_metadata_fetch *);
int hb_metadata_fetch_begin(struct hb_metadata_fetch *,const char *url,unsigned bytes,const unsigned char digest[32],const br_x509_trust_anchor *,size_t,const char *cache,unsigned long long reserve,unsigned timeout_ms,volatile int *,const struct ares_options *,int);
/* 0 more,1 verified bytes available,2 waiting for previous-cache choice,
 * negative terminal. Reads verified cache
 * with ownership/size/hash recheck; cache then explicitly discarded by task. */
int hb_metadata_fetch_step(struct hb_metadata_fetch *,unsigned wait_cap_ms);
int hb_metadata_fetch_cancel(struct hb_metadata_fetch *);
int hb_metadata_fetch_discard(struct hb_metadata_fetch *);
#endif
