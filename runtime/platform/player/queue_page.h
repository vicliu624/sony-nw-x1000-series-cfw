/* Private background queue read. Plans contain no borrowed Sony pointers. */
#ifndef XW_QUEUE_PAGE_H
#define XW_QUEUE_PAGE_H
#include "stock_media.h"
#include "stock_queue_owner.h"
struct xw_queue_plan {
 uint32_t generation,known_ids;
 uint64_t revision;
 struct xw_query_snapshot query;
 struct xw_stock_queue_cached_page source;
 uint32_t kind,group_limit; /* 0: copied flat order; 1: unshuffled group walk. */
 struct xw_stock_group_plan grouped;
};
struct xw_queue_result {
 uint32_t generation;
 struct xw_media_page page;
 struct xw_media_item items[XW_MEDIA_PAGE_MAX];
};
/* Workspace/output must be separate caller-owned storage, preferably heap/static.
 * Caller closes the transferred client after every attempt, including failures.
 * Generation is a task token, never a claimed native database revision. The
 * publisher must discard it if its current desired generation has changed. */
int xw_queue_page_read(struct xw_stock_media *,const struct xw_queue_plan *,struct xw_queue_result *workspace,struct xw_queue_result *out);
#endif
