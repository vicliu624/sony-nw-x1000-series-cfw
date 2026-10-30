#include "../../runtime/platform/player/group_native.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <string.h>
static struct xw_group_reader state;
static struct xw_group_native_workspace workspace;
static struct xw_queue_result out,prior;
static unsigned adopted,closed,read_calls,close_error;
int xw_stock_media_adopt(struct xw_stock_media *m){if(!m||!m->bound)return XW_PLAYER_CLOSED;adopted++;return 0;}
int xw_stock_media_close(struct xw_stock_media *m){assert(m->bound);if(close_error)return XW_PLAYER_IO;m->bound=0;closed++;return 0;}
int xw_stock_media_snapshot_page(struct xw_stock_media *m,const struct xw_query_snapshot *q,uint32_t offset,uint32_t limit,struct xw_stock_children_page *scratch,struct xw_stock_children_page *page){
 assert(m->bound);read_calls++;memset(scratch,0,sizeof *scratch);
 if(!q->kind){assert(limit==1&&offset==0);scratch->count=1;assert(!xw_local_media_id_format(1,100,&scratch->items[0].id));}
 else{assert(offset==0);scratch->count=1;scratch->exhausted=1;assert(!xw_local_media_id_format(1,7,&scratch->items[0].id));}*page=*scratch;return 0;
}
static int step(void){struct xw_stock_media m={0};m.bound=1;int rc=xw_group_native_step(&m,&state,&workspace,&out);assert(!m.bound);return rc;}
int main(void){struct xw_stock_group_plan plan={0};plan.total=1;assert(!xw_group_reader_begin(&state,&plan,1,0,2));memset(&out,0x5a,sizeof out);prior=out;
 assert(step()==XW_PLAYER_BUSY&&!memcmp(&out,&prior,sizeof out));assert(step()==XW_PLAYER_BUSY&&!memcmp(&out,&prior,sizeof out));assert(!step()&&out.page.count==1&&out.page.total==1&&adopted==3&&closed==3&&read_calls==2);
 prior=out;struct xw_stock_media m={0};m.bound=1;assert(xw_group_native_step(&m,&state,0,&out)==XW_PLAYER_INVALID&&!m.bound&&!memcmp(&out,&prior,sizeof out));
 close_error=1;m.bound=1;assert(xw_group_native_step(&m,&state,&workspace,&out)==XW_PLAYER_IO&&m.bound&&!memcmp(&out,&prior,sizeof out));close_error=0;assert(!xw_stock_media_close(&m));
 assert(xw_group_native_step(&m,&state,&workspace,&out)==XW_PLAYER_CLOSED);return 0;}
