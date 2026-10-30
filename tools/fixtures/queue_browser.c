#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/queue_browser.h"
#include "../../runtime/platform/player/local_identity.h"
#ifdef _WIN32
#include "windows_pthread.h"
#else
#include <pthread.h>
#endif
#include <stdatomic.h>
#include <assert.h>
#include <string.h>
#ifndef _WIN32
#include <unistd.h>
#endif
static struct xw_queue_browser browser;
static struct xw_stock_queue_owner owner;
static atomic_int stopping,opens,closes,grouped;
int xw_queue_capture(struct xw_stock_queue_owner *o,uint32_t session,uint32_t offset,uint32_t limit,uint32_t generation,struct xw_queue_capture_workspace *workspace,struct xw_queue_plan *out){
 (void)workspace;assert(o==&owner&&session==123);if(offset>5)return XW_PLAYER_INVALID;
 memset(out,0,sizeof *out);out->generation=generation;
 if(atomic_load(&grouped)){out->kind=1;out->group_limit=limit;out->source.order.offset=offset;out->grouped.total=3;return 0;}
 out->source.order.total=5;out->source.order.offset=offset;out->source.order.count=5-offset<limit?5-offset:limit;
 for(uint32_t i=0;i<out->source.order.count;i++)out->source.order.physical_indices[i]=4-offset-i;return 0;
}
int xw_stock_media_open(struct xw_stock_media *m){memset(m,0,sizeof *m);m->gui_owner=pthread_self();m->bound=1;atomic_fetch_add(&opens,1);return 0;}
int xw_stock_media_adopt(struct xw_stock_media *m){assert(m->gui_owner!=pthread_self());return 0;}
int xw_stock_media_close(struct xw_stock_media *m){assert(m->bound);m->bound=0;atomic_fetch_add(&closes,1);return 0;}
int xw_stock_media_fetch(struct xw_stock_media *m,const struct xw_media_id *id,struct xw_media_item *out){(void)m;(void)id;(void)out;assert(0);return -1;}
int xw_stock_media_snapshot_one(struct xw_stock_media *m,const struct xw_query_snapshot *q,uint32_t index,struct xw_media_item *out){(void)m;(void)q;memset(out,0,sizeof *out);memcpy(out->title,"song",5);out->flags=XW_MEDIA_TITLE_PRESENT;return xw_local_media_id_format(0,index,&out->id);}
static void *met(void *p){(void)p;while(!atomic_load(&stopping)){int rc=xw_queue_browser_capture(&browser,&owner,123);assert(rc==0||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE||rc==XW_PLAYER_STALE);usleep(1000);}return 0;}
static struct xw_media_item items[16];static struct xw_media_page page;
static void read_page(unsigned offset,unsigned count){
 struct xw_media_query q={0};q.view=XW_MEDIA_QUEUE;q.offset=offset;q.limit=2;
 int rc=-1;for(int i=0;i<5000&&rc;i++){rc=xw_queue_browser_browse(&browser,&q,10+i,&items[0],&page);assert(!rc||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);usleep(1000);}assert(!rc&&page.offset==offset&&page.count==count&&page.total==5&&page.revision==0);
 for(unsigned i=0;i<count;i++){struct xw_media_id id;assert(!xw_local_media_id_format(0,4-offset-i,&id));assert(!strcmp(id.value,items[i].id.value)&&!strcmp(items[i].title,"song"));}
}
static void read_group_page(unsigned offset,unsigned count){
 struct xw_media_query q={0};q.view=XW_MEDIA_QUEUE;q.offset=offset;q.limit=2;int rc=XW_PLAYER_BUSY;
 for(unsigned i=0;i<5000&&rc;i++){rc=xw_queue_browser_browse(&browser,&q,1000+i,items,&page);assert(!rc||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);usleep(1000);}
 assert(!rc&&page.offset==offset&&page.count==count&&(page.total==5||page.total==XW_MEDIA_TOTAL_UNKNOWN));
 for(unsigned i=0;i<count;i++){uint32_t d,n;assert(!xw_local_media_id_parse(&items[i].id,&d,&n)&&n==offset+i+1&&!memcmp(items[i].title,"group",6));}
}
int main(void){
 assert(!xw_queue_browser_init(&browser));pthread_t thread;assert(!pthread_create(&thread,0,met,0));read_page(0,2);read_page(2,2);read_page(4,1);atomic_store(&grouped,1);read_group_page(1,2);read_group_page(4,1);
 struct xw_media_query q={0};q.view=XW_MEDIA_QUEUE;q.offset=4;q.limit=2;q.expected_revision=1;struct xw_media_page prior=page;assert(xw_queue_browser_browse(&browser,&q,20,items,&page)==XW_PLAYER_STALE&&!memcmp(&page,&prior,sizeof page));
 int rc;do{rc=xw_queue_browser_revoke(&browser,21);}while(rc==XW_PLAYER_BUSY);assert(!rc);
 atomic_store(&stopping,1);assert(!pthread_join(thread,0));do{rc=xw_queue_browser_close(&browser);if(rc)usleep(1000);}while(rc==XW_PLAYER_BUSY);assert(!rc&&atomic_load(&opens)==atomic_load(&closes));return 0;
}

int xw_stock_media_snapshot_page(struct xw_stock_media *m,const struct xw_query_snapshot *q,uint32_t offset,uint32_t limit,struct xw_stock_children_page *w,struct xw_stock_children_page *out){
 assert(m->bound);memset(w,0,sizeof *w);
 if(!q->kind){assert(offset<3&&limit==1);w->count=1;assert(!xw_local_media_id_format(1,10+offset,&w->items[0].id));}
 else{uint32_t domain,group;assert(!xw_local_media_id_parse(&q->parent,&domain,&group)&&group>=10&&group<=12);const uint32_t count[3]={2,0,3},start[3]={1,0,3};
  for(uint32_t i=offset;i<count[group-10]&&w->count<limit;i++){struct xw_media_item *item=&w->items[w->count++];assert(!xw_local_media_id_format(1,start[group-10]+i,&item->id));memcpy(item->title,"group",6);item->flags=XW_MEDIA_TITLE_PRESENT;}
  w->exhausted=offset+w->count>=count[group-10];
 }*out=*w;return 0;
}
