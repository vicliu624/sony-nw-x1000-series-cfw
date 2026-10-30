/* Dedicated queue worker. Owner operations never wait for a Moma read. */
#ifndef XW_QUEUE_ASYNC_H
#define XW_QUEUE_ASYNC_H
#include "queue_page.h"
#include "metadata_async.h"
#include "group_native.h"
struct xw_queue_async {
 union xw_pthread_storage mutex,condition;
 unsigned initialized,started,closing,exited,phase,desired_valid,cache_valid;
 unsigned long owner,thread;
 uint64_t epoch,job_epoch,result_epoch,last,next_attempt;
 struct xw_queue_plan desired,job;
 struct xw_stock_media media;
 struct xw_queue_result workspace,result,cache;
 struct xw_group_reader group_reader;
 struct xw_group_native_workspace group_workspace;
 uint64_t group_epoch;
 unsigned result_progress;
 int result_code,status;
};
int xw_queue_async_init(struct xw_queue_async *);
/* Owner only. NULL revokes all cached/pending intent. Caller must supply a
 * current owner-captured plan, not a retained Sony pointer. Output is unchanged
 * while unavailable. Result generation alone never establishes freshness. */
int xw_queue_async_observe(struct xw_queue_async *,const struct xw_queue_plan *,uint64_t now_ms,struct xw_queue_result *);
int xw_queue_async_stop(struct xw_queue_async *);
int xw_queue_async_drained(struct xw_queue_async *);
int xw_queue_async_destroy(struct xw_queue_async *);
#endif
