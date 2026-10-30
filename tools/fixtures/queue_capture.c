#include "../../runtime/platform/player/queue_capture.h"
#include <assert.h>
#include <string.h>
static struct xw_queue_capture_workspace work;
static int failure,held,releases,all_cached,query_calls,group_mode;
int xw_stock_queue_owner_acquire(struct xw_stock_queue_owner *s,uint32_t session){(void)s;(void)session;if(failure==1)return XW_PLAYER_BUSY;assert(!held);held=1;return 0;}
int xw_stock_queue_owner_release(struct xw_stock_queue_owner *s){(void)s;assert(held);held=0;releases++;return failure==4?XW_PLAYER_IO:0;}
int xw_stock_queue_owner_cached_partial(struct xw_stock_queue_owner *s,uint32_t offset,uint32_t limit,struct xw_stock_queue_partial_page *out){(void)s;(void)limit;assert(held);if(group_mode)return XW_PLAYER_UNSUPPORTED;if(failure==2)return XW_PLAYER_BUSY;memset(out,0,sizeof *out);out->page.order.offset=offset;out->page.order.total=10;out->page.order.count=1;out->page.order.physical_indices[0]=3;if(all_cached)out->known_ids=1;return 0;}
int xw_stock_queue_owner_query(struct xw_stock_queue_owner *s,struct xw_query_snapshot *out){(void)s;assert(held);query_calls++;if(failure==3)return XW_PLAYER_UNSUPPORTED;memset(out,0,sizeof *out);if(failure==5)out->root=1;return 0;}
int main(void){struct xw_stock_queue_owner owner={0};struct xw_queue_plan out,before;memset(&out,0x5a,sizeof out);before=out;
 for(failure=1;failure<=5;failure++){int n=releases;assert(xw_queue_capture(&owner,1,0,1,8,&work,&out)<0);assert(!held&&!memcmp(&out,&before,sizeof out));assert(releases==n+(failure!=1));}
 failure=0;assert(!xw_queue_capture(&owner,1,2,1,8,&work,&out));assert(!held&&out.generation==8&&out.revision==0&&out.source.order.offset==2&&out.source.order.physical_indices[0]==3&&!out.known_ids);
 all_cached=1;int prior_queries=query_calls;assert(!xw_queue_capture(&owner,1,0,1,9,&work,&out)&&out.known_ids==1&&query_calls==prior_queries);
 group_mode=1;assert(!xw_queue_capture(&owner,1,2,3,10,&work,&out)&&out.kind==1&&out.group_limit==3&&out.source.order.offset==2&&out.revision==0);
 before=out;group_mode=2;assert(xw_queue_capture(&owner,1,0,3,11,&work,&out)==XW_PLAYER_UNSUPPORTED&&!memcmp(&out,&before,sizeof out)&&!held);
 assert(xw_queue_capture(&owner,1,0,1,12,&work,&work.value)==XW_PLAYER_INVALID);
 int n=releases;assert(xw_queue_capture(&owner,1,0,1,0,&work,&out)==XW_PLAYER_INVALID&&releases==n);return 0;}

int xw_stock_queue_owner_group_plan(struct xw_stock_queue_owner *s,struct xw_stock_group_plan *p){(void)s;if(!group_mode)return XW_PLAYER_UNSUPPORTED;memset(p,0,sizeof *p);p->total=2;p->shuffled=group_mode==2;return 0;}
