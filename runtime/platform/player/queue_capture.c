#include "queue_capture.h"
#include <stddef.h>
#include <string.h>
static int overlap(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
int xw_queue_capture(struct xw_stock_queue_owner *owner,uint32_t session,uint32_t offset,uint32_t limit,uint32_t generation,struct xw_queue_capture_workspace *workspace,struct xw_queue_plan *out){
 if(!owner||!out||!workspace||!generation||!limit||limit>XW_MEDIA_PAGE_MAX||offset>UINT32_MAX-limit||overlap(workspace,sizeof *workspace,out,sizeof *out)||overlap(workspace,sizeof *workspace,owner,sizeof *owner)||overlap(out,sizeof *out,owner,sizeof *owner))return XW_PLAYER_INVALID;
 int rc=xw_stock_queue_owner_acquire(owner,session);if(rc)return rc;
 struct xw_queue_plan *value=&workspace->value;memset(value,0,sizeof *value);
 struct xw_stock_queue_partial_page *cached=&workspace->cached;
 rc=xw_stock_queue_owner_cached_partial(owner,offset,limit,cached);
 if(rc==XW_PLAYER_UNSUPPORTED){
  rc=xw_stock_queue_owner_group_plan(owner,&value->grouped);
  if(!rc&&value->grouped.shuffled)rc=XW_PLAYER_UNSUPPORTED;
  if(!rc){value->kind=1;value->group_limit=limit;value->source.order.offset=offset;value->source.order.total=XW_MEDIA_TOTAL_UNKNOWN;}
 }else if(!rc){value->source=cached->page;value->known_ids=cached->known_ids;
  if(value->known_ids!=((1u<<value->source.order.count)-1u))rc=xw_stock_queue_owner_query(owner,&value->query);
  if(!rc)rc=xw_query_snapshot_validate(&value->query);
 }
 int release=xw_stock_queue_owner_release(owner);if(release)return release;
 if(rc)return rc;value->generation=generation;/* Native revision remains unknown. */
 *out=*value;return 0;
}
