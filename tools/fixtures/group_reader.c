#include "../../runtime/platform/player/group_reader.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <string.h>
static struct xw_group_reader state;
static struct xw_stock_group_plan plan;
static struct xw_queue_result out,before;
static unsigned reads,fault,bad_group,missing_group;
static int page_read(void *ctx,const struct xw_query_snapshot *query,uint32_t offset,uint32_t limit,struct xw_stock_children_page *page){
 (void)ctx;reads++;if(reads==fault)return XW_PLAYER_IO;memset(page,0,sizeof *page);
 if(!query->kind){
  assert(limit==1);if(offset>=3||missing_group){page->exhausted=1;return 0;}page->count=1;
  if(bad_group)memcpy(page->items[0].id.value,"bad",4);else assert(!xw_local_media_id_format(1,10+offset,&page->items[0].id));return 0;
 }
 uint32_t domain,group;assert(!xw_local_media_id_parse(&query->parent,&domain,&group)&&domain==1&&group>=10&&group<=12);assert(limit==16);
 const unsigned counts[3]={2,0,3},starts[3]={1,0,3};unsigned n=counts[group-10];
 for(unsigned i=offset;i<n&&page->count<limit;i++)assert(!xw_local_media_id_format(1,starts[group-10]+i,&page->items[page->count++].id));
 page->exhausted=offset+page->count>=n;return 0;
}
static int run(unsigned offset,unsigned limit){
 reads=0;assert(!xw_group_reader_begin(&state,&plan,9,offset,limit));int rc=XW_PLAYER_BUSY;
 for(unsigned i=0;i<100&&rc==XW_PLAYER_BUSY;i++){unsigned old=reads;rc=xw_group_reader_step(&state,page_read,0,&out);assert(reads-old<=1);}
 assert(rc!=XW_PLAYER_BUSY);return rc;
}
int main(void){
 plan.total=3;assert(!run(1,3));assert(out.generation==9&&out.page.count==3&&out.page.offset==1&&out.page.next_offset==4&&out.page.total==XW_MEDIA_TOTAL_UNKNOWN);
 for(unsigned i=0;i<3;i++){uint32_t d,n;assert(!xw_local_media_id_parse(&out.items[i].id,&d,&n)&&n==i+2);}
 assert(!run(4,3)&&out.page.count==1&&out.page.total==5);
 plan.total=UINT32_MAX;assert(!run(0,16)&&out.page.count==5&&out.page.total==5);plan.total=3;
 before=out;assert(run(6,2)==XW_PLAYER_INVALID&&!memcmp(&out,&before,sizeof out));xw_group_reader_reset(&state);
 fault=2;assert(run(0,2)==XW_PLAYER_IO&&!memcmp(&out,&before,sizeof out));fault=0;xw_group_reader_reset(&state);
 bad_group=1;assert(run(0,2)==XW_PLAYER_PROTOCOL&&!memcmp(&out,&before,sizeof out));bad_group=0;xw_group_reader_reset(&state);
 missing_group=1;assert(run(0,2)==XW_PLAYER_STALE&&!memcmp(&out,&before,sizeof out));missing_group=0;xw_group_reader_reset(&state);
 plan.shuffled=1;assert(xw_group_reader_begin(&state,&plan,9,0,2)==XW_PLAYER_UNSUPPORTED);plan.shuffled=0;
 assert(!xw_group_reader_begin(&state,&plan,9,0,2));assert(xw_group_reader_begin(&state,&plan,10,0,2)==XW_PLAYER_BUSY);xw_group_reader_reset(&state);
 assert(xw_group_reader_step(&state,page_read,0,&out)==XW_PLAYER_CLOSED);return 0;
}

