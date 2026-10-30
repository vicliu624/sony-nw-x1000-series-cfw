#include "group_native.h"
#include <stddef.h>
struct read_context {struct xw_stock_media *media;struct xw_group_native_workspace *workspace;};
static int overlap(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
static int page_read(void *argument,const struct xw_query_snapshot *query,uint32_t offset,uint32_t limit,struct xw_stock_children_page *out){
 struct read_context *c=argument;return xw_stock_media_snapshot_page(c->media,query,offset,limit,&c->workspace->page,out);
}
int xw_group_native_step(struct xw_stock_media *media,struct xw_group_reader *state,struct xw_group_native_workspace *workspace,struct xw_queue_result *out){
 int rc=xw_stock_media_adopt(media);if(rc)return rc;
 if(!state||!workspace||!out||overlap(workspace,sizeof *workspace,state,sizeof *state)||overlap(workspace,sizeof *workspace,out,sizeof *out)||overlap(out,sizeof *out,state,sizeof *state)||overlap(media,sizeof *media,state,sizeof *state)||overlap(media,sizeof *media,workspace,sizeof *workspace)||overlap(media,sizeof *media,out,sizeof *out))rc=XW_PLAYER_INVALID;
 else{struct read_context c={media,workspace};rc=xw_group_reader_step(state,page_read,&c,&workspace->result);}
 int closed=xw_stock_media_close(media);if(closed)return closed;
 if(!rc)*out=workspace->result;return rc;
}
