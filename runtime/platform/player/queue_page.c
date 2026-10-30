#include "queue_page.h"
#include "local_identity.h"
#include <string.h>
static int overlaps(const void *a,size_t an,const void *b,size_t bn){
 uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;
}
int xw_queue_page_read(struct xw_stock_media *media,const struct xw_queue_plan *p,struct xw_queue_result *w,struct xw_queue_result *out){
 int rc=xw_stock_media_adopt(media);if(rc)return rc;
 if(!p||!w||!out)return XW_PLAYER_INVALID;
 if(p->kind)return XW_PLAYER_UNSUPPORTED;
 if(overlaps(p,sizeof *p,w,sizeof *w)||overlaps(p,sizeof *p,out,sizeof *out)||overlaps(w,sizeof *w,out,sizeof *out)||overlaps(media,sizeof *media,w,sizeof *w)||overlaps(media,sizeof *media,out,sizeof *out)||overlaps(media,sizeof *media,p,sizeof *p))return XW_PLAYER_INVALID;
 const struct xw_stock_queue_order_page *order=&p->source.order;
 if(!p->generation||order->count>XW_MEDIA_PAGE_MAX||order->offset>order->total||order->count>order->total-order->offset||order->shuffled>1)return XW_PLAYER_PROTOCOL;
 if(p->known_ids&~((1u<<order->count)-1u))return XW_PLAYER_PROTOCOL;
 rc=xw_query_snapshot_validate(&p->query);if(rc)return rc;
 for(uint32_t i=0;i<order->count;i++){
  if(order->physical_indices[i]>=order->total)return XW_PLAYER_PROTOCOL;
  if(p->known_ids&(1u<<i)){uint32_t domain,number;rc=xw_local_media_id_parse(&p->source.ids[i],&domain,&number);if(rc)return XW_PLAYER_PROTOCOL;}
 }
 memset(w,0,sizeof *w);w->generation=p->generation;
 w->page.revision=p->revision;w->page.offset=order->offset;w->page.count=order->count;w->page.total=order->total;w->page.next_offset=order->offset+order->count;
 for(uint32_t i=0;i<order->count;i++){
  if(p->known_ids&(1u<<i)){
   rc=xw_stock_media_fetch(media,&p->source.ids[i],&w->items[i]);
   if(!rc&&strcmp(w->items[i].id.value,p->source.ids[i].value))rc=XW_PLAYER_STALE;
  }else rc=xw_stock_media_snapshot_one(media,&p->query,order->physical_indices[i],&w->items[i]);
  if(rc)return rc;
 }
 *out=*w;return 0;
}
