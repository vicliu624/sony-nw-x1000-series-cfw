/* Owner-only capture; no native reference escapes into a read plan. */
#ifndef XW_QUEUE_CAPTURE_H
#define XW_QUEUE_CAPTURE_H
#include "queue_page.h"
/* Must run in a qualified Met callback. owner must be bound and not already
 * holding a sequence. Generation identifies caller intent, not a DB revision. */
struct xw_queue_capture_workspace {struct xw_queue_plan value;struct xw_stock_queue_partial_page cached;};
int xw_queue_capture(struct xw_stock_queue_owner *,uint32_t session,uint32_t offset,uint32_t limit,uint32_t generation,struct xw_queue_capture_workspace *,struct xw_queue_plan *);
#endif
