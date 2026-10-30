/* Private coordinator; caller must establish and quiesce the Met callback. */
#ifndef XW_QUEUE_BROWSER_H
#define XW_QUEUE_BROWSER_H
#include "queue_exchange.h"
#include "queue_async.h"
struct xw_queue_browser {
 struct xw_queue_exchange exchange;
 struct xw_queue_async reader;
 struct xw_queue_plan gui_plan,met_plan;
 struct xw_queue_capture_workspace capture_workspace;
 struct xw_queue_result result;
 unsigned initialized;
};
int xw_queue_browser_init(struct xw_queue_browser *);
/* Qualified Met callback only; owner must be bound on that thread. */
int xw_queue_browser_capture(struct xw_queue_browser *,struct xw_stock_queue_owner *,uint32_t session);
/* GUI only. A failed source observation must call revoke before serving data. */
int xw_queue_browser_browse(struct xw_queue_browser *,const struct xw_media_query *,uint64_t now,struct xw_media_item *,struct xw_media_page *);
int xw_queue_browser_revoke(struct xw_queue_browser *,uint64_t now);
/* GUI only AFTER Met callback access is quiesced externally. May return BUSY
 * while a native worker read drains; call again, retaining the context. */
int xw_queue_browser_close(struct xw_queue_browser *);
#endif
