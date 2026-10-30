#include "queue_browser.h"
#include <string.h>
#define BOUND 0x58575142u
int xw_queue_browser_init(struct xw_queue_browser *b){
 if(!b)return XW_PLAYER_INVALID;if(b->initialized)return XW_PLAYER_BUSY;memset(b,0,sizeof *b);
 int rc=xw_queue_exchange_init(&b->exchange);if(rc)return rc;
 rc=xw_queue_async_init(&b->reader);if(rc){xw_queue_exchange_destroy(&b->exchange);return rc;}
 b->initialized=BOUND;return 0;
}
int xw_queue_browser_capture(struct xw_queue_browser *b,struct xw_stock_queue_owner *owner,uint32_t session){
 if(!b||b->initialized!=BOUND)return XW_PLAYER_CLOSED;
 struct xw_queue_request request;int rc=xw_queue_exchange_take(&b->exchange,&request);if(rc)return rc;
 rc=xw_queue_capture(owner,session,request.offset,request.limit,request.generation,&b->capture_workspace,&b->met_plan);
 return xw_queue_exchange_publish(&b->exchange,&request,rc,rc?0:&b->met_plan);
}
int xw_queue_browser_revoke(struct xw_queue_browser *b,uint64_t now){
 if(!b||b->initialized!=BOUND)return XW_PLAYER_CLOSED;
 int rc=xw_queue_exchange_request(&b->exchange,0,0);if(rc)return rc;
 rc=xw_queue_async_observe(&b->reader,0,now,&b->result);
 return rc==XW_PLAYER_UNAVAILABLE?0:rc;
}
int xw_queue_browser_browse(struct xw_queue_browser *b,const struct xw_media_query *q,uint64_t now,struct xw_media_item *items,struct xw_media_page *page){
 if(!b||b->initialized!=BOUND)return XW_PLAYER_CLOSED;
 if(!q||!items||!page||q->view!=XW_MEDIA_QUEUE||q->container.value[0]||!q->limit||q->limit>XW_MEDIA_PAGE_MAX||q->offset>UINT32_MAX-q->limit)return XW_PLAYER_INVALID;
 int rc=xw_queue_exchange_request(&b->exchange,q->offset,q->limit);if(rc)return rc;
 rc=xw_queue_exchange_read(&b->exchange,&b->gui_plan);
 if(rc){xw_queue_async_observe(&b->reader,0,now,&b->result);return rc;}
 if(q->expected_revision&&q->expected_revision!=b->gui_plan.revision){xw_queue_async_observe(&b->reader,0,now,&b->result);return XW_PLAYER_STALE;}
 rc=xw_queue_async_observe(&b->reader,&b->gui_plan,now,&b->result);if(rc)return rc;
 if(b->result.generation!=b->gui_plan.generation||b->result.page.offset!=q->offset||b->result.page.count>q->limit)return XW_PLAYER_PROTOCOL;
 memcpy(items,b->result.items,b->result.page.count*sizeof *items);*page=b->result.page;return 0;
}
int xw_queue_browser_close(struct xw_queue_browser *b){
 if(!b||b->initialized!=BOUND)return XW_PLAYER_CLOSED;
 int rc=0;if(b->reader.initialized){rc=xw_queue_async_stop(&b->reader);if(rc<0)return rc;if(!xw_queue_async_drained(&b->reader))return XW_PLAYER_BUSY;
 rc=xw_queue_async_destroy(&b->reader);if(rc)return rc;}
 rc=xw_queue_exchange_destroy(&b->exchange);if(rc)return rc;
 b->initialized=0;return 0;
}
