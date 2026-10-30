#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/queue_async.h"
#ifdef _WIN32
#include "windows_pthread.h"
#else
#include <pthread.h>
#endif
#include <stdatomic.h>
#include <assert.h>
#include "../../runtime/platform/player/local_identity.h"
#include <string.h>
#ifndef _WIN32
#include <unistd.h>
#endif
static atomic_int entered,release_read,closed,opened;
static struct xw_queue_async service;
static struct xw_queue_plan plan;
static struct xw_queue_result out,before;
int xw_stock_media_open(struct xw_stock_media *s){memset(s,0,sizeof *s);s->bound=1;s->gui_owner=pthread_self();atomic_fetch_add(&opened,1);return 0;}
int xw_stock_media_close(struct xw_stock_media *s){assert(s->bound);s->bound=0;atomic_fetch_add(&closed,1);return 0;}
int xw_queue_page_read(struct xw_stock_media *s,const struct xw_queue_plan *p,struct xw_queue_result *w,struct xw_queue_result *result){
 assert(s->gui_owner!=pthread_self());atomic_fetch_add(&entered,1);while(!atomic_load(&release_read))usleep(1000);
 memset(w,0,sizeof *w);w->generation=p->generation;w->page.total=p->source.order.total;*result=*w;return 0;
}
int xw_stock_media_adopt(struct xw_stock_media *m){assert(m->bound&&m->gui_owner!=pthread_self());return 0;}
int xw_stock_media_snapshot_page(struct xw_stock_media *m,const struct xw_query_snapshot *q,uint32_t offset,uint32_t limit,struct xw_stock_children_page *scratch,struct xw_stock_children_page *page){
 (void)m;(void)offset;(void)limit;atomic_fetch_add(&entered,1);while(!atomic_load(&release_read))usleep(1000);memset(scratch,0,sizeof *scratch);scratch->count=1;scratch->exhausted=1;
 assert(!xw_local_media_id_format(1,q->kind?7:100,&scratch->items[0].id));memcpy(scratch->items[0].title,"child",6);*page=*scratch;return 0;
}
static void await_count(atomic_int *value,int count){for(int i=0;i<5000&&atomic_load(value)<count;i++)usleep(1000);assert(atomic_load(value)>=count);}
static int observe(uint64_t now){return xw_queue_async_observe(&service,&plan,now,&out);}
int main(void){
 assert(!xw_queue_async_init(&service));plan.generation=1;plan.source.order.total=10;memset(&out,0x5a,sizeof out);before=out;
 assert(observe(0)==XW_PLAYER_BUSY);await_count(&entered,1);
 /* Same caller generation, different captured order: internal epoch must change. */
 plan.source.order.total=20;assert(observe(1)==XW_PLAYER_UNAVAILABLE);assert(!memcmp(&out,&before,sizeof out));
 atomic_store(&release_read,1);await_count(&closed,1);
 int rc=XW_PLAYER_BUSY;for(int i=0;i<5000&&rc;i++){rc=observe(2);if(rc)assert(!memcmp(&out,&before,sizeof out));usleep(1000);}assert(!rc&&out.page.total==20);assert(atomic_load(&entered)==2);
 before=out;assert(xw_queue_async_observe(&service,0,3,&out)==XW_PLAYER_UNAVAILABLE);assert(!memcmp(&out,&before,sizeof out));
 /* Revoke while a read is running, then close without waiting in stop(). */
 atomic_store(&release_read,0);plan.generation=3;assert(observe(4)==XW_PLAYER_BUSY);await_count(&entered,3);
 assert(xw_queue_async_observe(&service,0,5,&out)==XW_PLAYER_UNAVAILABLE);assert(!memcmp(&out,&before,sizeof out));
 assert(xw_queue_async_stop(&service)==XW_PLAYER_ACCEPTED);assert(!xw_queue_async_drained(&service));assert(xw_queue_async_destroy(&service)==XW_PLAYER_BUSY);
 atomic_store(&release_read,1);for(int i=0;i<5000&&!xw_queue_async_drained(&service);i++)usleep(1000);
 assert(xw_queue_async_drained(&service));assert(atomic_load(&opened)==atomic_load(&closed));assert(!xw_queue_async_destroy(&service));
 assert(!xw_queue_async_init(&service));memset(&plan,0,sizeof plan);plan.kind=1;plan.generation=10;plan.group_limit=2;plan.grouped.total=1;atomic_store(&release_read,1);
 uint64_t now=100;rc=XW_PLAYER_BUSY;for(unsigned i=0;i<5000&&rc;i++){rc=observe(now++);assert(!rc||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);usleep(1000);}assert(!rc&&out.generation==10&&out.page.count==1&&out.page.total==1&&!memcmp(out.items[0].title,"child",6));
 before=out;int count=atomic_load(&opened);plan.grouped.current=UINT32_MAX;assert(!observe(now++)&&atomic_load(&opened)==count);
 /* Unused capacity and struct padding do not change a valid query. */
 plan.grouped.groups.nodes[31].operation=123;plan.grouped.groups.sort[15].key=456;
 unsigned char *padding=(unsigned char *)&plan.grouped.groups.parent+sizeof plan.grouped.groups.parent;
 if(padding<(unsigned char *)plan.grouped.groups.nodes)*padding=0x5a;
 assert(!observe(now++)&&atomic_load(&opened)==count);
 plan.grouped.groups.sort_count=1;plan.grouped.groups.sort[0].key=9;
 assert(observe(now++)==XW_PLAYER_BUSY&&atomic_load(&opened)==count+1);
 rc=XW_PLAYER_BUSY;for(unsigned i=0;i<5000&&rc;i++){rc=observe(now++);assert(!rc||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);usleep(1000);}assert(!rc);before=out;
 atomic_store(&release_read,0);plan.generation=11;int next=atomic_load(&entered)+1;assert(observe(now++)==XW_PLAYER_BUSY);await_count(&entered,next);
 assert(xw_queue_async_observe(&service,0,now++,&out)==XW_PLAYER_UNAVAILABLE&&!memcmp(&out,&before,sizeof out));assert(xw_queue_async_stop(&service)==XW_PLAYER_ACCEPTED);atomic_store(&release_read,1);
 for(unsigned i=0;i<5000&&!xw_queue_async_drained(&service);i++)usleep(1000);assert(xw_queue_async_drained(&service));assert(!xw_queue_async_destroy(&service));assert(atomic_load(&opened)==atomic_load(&closed));
 return 0;
}
