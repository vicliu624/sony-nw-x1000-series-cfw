#include "../../runtime/platform/player/queue_page.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <string.h>
static unsigned reads,adopts,fail_at;
int xw_stock_media_adopt(struct xw_stock_media *m){adopts++;return m?0:XW_PLAYER_CLOSED;}
int xw_stock_media_fetch(struct xw_stock_media *m,const struct xw_media_id *id,struct xw_media_item *out){(void)m;reads++;if(reads==fail_at)return XW_PLAYER_IO;out->id=*id;strcpy(out->title,"cached");return 0;}
int xw_stock_media_snapshot_one(struct xw_stock_media *m,const struct xw_query_snapshot *q,uint32_t index,struct xw_media_item *out){(void)m;(void)q;reads++;if(reads==fail_at)return XW_PLAYER_STALE;strcpy(out->title,"query");return xw_local_media_id_format(0,index,&out->id);}
static struct xw_queue_plan plan;
static struct xw_queue_result scratch,out,before;
int main(void){
 struct xw_stock_media media={0};plan.generation=7;plan.source.order.total=5;plan.source.order.count=2;plan.source.order.physical_indices[0]=4;plan.source.order.physical_indices[1]=1;plan.source.order.shuffled=1;plan.known_ids=1;
 assert(!xw_local_media_id_format(0,99,&plan.source.ids[0]));
 assert(!xw_queue_page_read(&media,&plan,&scratch,&out));assert(reads==2&&out.generation==7&&out.page.total==5&&out.page.revision==0);assert(!strcmp(out.items[0].title,"cached")&&!strcmp(out.items[1].title,"query"));
 struct xw_media_id expected;assert(!xw_local_media_id_format(0,1,&expected));assert(!strcmp(out.items[1].id.value,expected.value));
 before=out;reads=0;fail_at=2;assert(xw_queue_page_read(&media,&plan,&scratch,&out)==XW_PLAYER_STALE);assert(!memcmp(&out,&before,sizeof out));fail_at=0;
 plan.known_ids=4;reads=0;assert(xw_queue_page_read(&media,&plan,&scratch,&out)==XW_PLAYER_PROTOCOL&&!reads);assert(!memcmp(&out,&before,sizeof out));
 plan.known_ids=1;plan.source.order.physical_indices[1]=5;assert(xw_queue_page_read(&media,&plan,&scratch,&out)==XW_PLAYER_PROTOCOL);plan.source.order.physical_indices[1]=1;
 assert(xw_queue_page_read(&media,&plan,&out,&out)==XW_PLAYER_INVALID);
 plan.source.order.count=0;plan.known_ids=0;assert(!xw_queue_page_read(&media,&plan,&scratch,&out)&&!out.page.count);
 assert(xw_queue_page_read(&media,0,&scratch,&out)==XW_PLAYER_INVALID);assert(adopts==7);
 return 0;
}

