/* Private bounded background Moma reader; GUI-owned cache and request epochs. */
#ifndef XW_PLAYER_METADATA_ASYNC_H
#define XW_PLAYER_METADATA_ASYNC_H
#include "stock_media.h"
union xw_pthread_storage {uint64_t alignment;unsigned char bytes[64];};
struct xw_children_async;
struct xw_metadata_async {
    struct xw_children_async *children;
    int (*read_item)(struct xw_stock_media *,const struct xw_media_id *,struct xw_media_item *); /* immutable before worker start */
    union xw_pthread_storage mutex,condition;
    unsigned initialized,started,closing,exited,phase;
    unsigned long owner,thread;
    uint32_t generation,job_generation,result_generation;
    uint64_t revision,job_revision;
    unsigned long long last,next_attempt;
    struct xw_media_id desired,job_id;
    struct xw_stock_media job_media;
    struct xw_media_item result,cache;
    int result_code,status; /* status is GUI-owned; result_code is mutex-protected */
    unsigned cache_valid;
};
int xw_metadata_async_init(struct xw_metadata_async *);
/* Owner only, nonblocking on its own mutex. NULL ID revokes the cache and
 * pending intent. Results are merged only for the current ID/revision epoch.
 * A supported source must be ready before requesting/using cached metadata. */
int xw_metadata_async_observe(struct xw_metadata_async *,const struct xw_media_id *,uint64_t revision,unsigned long long now_ms,struct xw_media_item *);
int xw_metadata_async_stop(struct xw_metadata_async *);
int xw_metadata_async_drained(struct xw_metadata_async *);
int xw_metadata_async_destroy(struct xw_metadata_async *);
/* Dedicated instance, sharing the worker/lifecycle implementation. The caller
 * supplies revision epochs; zero means no qualified catalog revision. NULL
 * query revokes pending intent/results. No original handles are cached. */
struct xw_children_async {
    struct xw_metadata_async worker;
    struct xw_stock_children_query desired,job;
    struct xw_stock_children_page result,cache;
    unsigned desired_valid;
    int status;
};
int xw_children_async_init(struct xw_children_async *);
int xw_children_async_observe(struct xw_children_async *,const struct xw_stock_children_query *,uint64_t revision,unsigned long long now_ms,struct xw_stock_children_page *);
#endif
