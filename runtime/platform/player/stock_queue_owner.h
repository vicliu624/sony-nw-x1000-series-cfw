/* Private Met-owner reference adapter; no GUI acquisition or queue enumeration. */
#ifndef XW_STOCK_QUEUE_OWNER_H
#define XW_STOCK_QUEUE_OWNER_H
#include "player.h"
#include "query_snapshot.h"
#include "session_identity.h"
struct xw_stock_queue_owner {unsigned bound,busy;unsigned long owner;uint32_t sequence;};
/* Bind/acquire/release must run in a separately qualified original Met owner
 * callback. Recording pthread_self is an affinity guard, not proof that the
 * caller owns Met. Never bind this from GUI/metadata workers or expose it in SDK. */
int xw_stock_queue_owner_bind(struct xw_stock_queue_owner *);
/* Qualified Met callback supplies its r7 list identity; compare values only.
 * The retained callback session supplies the native number at+0x14. */
int xw_stock_queue_owner_session_matches(struct xw_stock_queue_owner *,uint32_t session,uint32_t callback_list,const struct xw_stock_session_key *);
int xw_stock_queue_owner_acquire(struct xw_stock_queue_owner *,uint32_t session);
int xw_stock_queue_owner_release(struct xw_stock_queue_owner *);
struct xw_stock_queue_order_page {uint32_t total,offset,count,shuffled;uint32_t physical_indices[XW_MEDIA_PAGE_MAX];};
/* Owner-only order snapshot for qualified OneGrp with MmTrk or prepared
 * MmOneTrk implementations.
 * Physical ordinals are not media IDs and are never exposed as SDK rows. */
int xw_stock_queue_owner_order(struct xw_stock_queue_owner *,uint32_t offset,uint32_t limit,struct xw_stock_queue_order_page *);
struct xw_stock_queue_cached_page {struct xw_stock_queue_order_page order;struct xw_media_id ids[XW_MEDIA_PAGE_MAX];};
/* Nonblocking idle-cache snapshot only. Misses return UNAVAILABLE; no query or
 * LRU mutation occurs. The caller must satisfy the same Met owner precondition. */
int xw_stock_queue_owner_cached_ids(struct xw_stock_queue_owner *,uint32_t offset,uint32_t limit,struct xw_stock_queue_cached_page *);
struct xw_stock_queue_partial_page {struct xw_stock_queue_cached_page page;uint32_t known_ids;};
/* Missing cache entries remain zero; corrupt entries still fail atomically. */
int xw_stock_queue_owner_cached_partial(struct xw_stock_queue_owner *,uint32_t offset,uint32_t limit,struct xw_stock_queue_partial_page *);
int xw_stock_queue_owner_query(struct xw_stock_queue_owner *,struct xw_query_snapshot *);
/* Read-only group descriptor, not a flattened queue or a mutable sequence. */
struct xw_stock_group_plan {struct xw_query_snapshot groups,track_filter;uint32_t total,current,shuffled;};
int xw_stock_queue_owner_group_plan(struct xw_stock_queue_owner *,struct xw_stock_group_plan *);
int xw_stock_queue_owner_unbind(struct xw_stock_queue_owner *);
#endif
