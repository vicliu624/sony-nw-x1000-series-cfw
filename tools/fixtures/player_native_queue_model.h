/* Native boundaries modeled; production host/capture/exchange/readers execute. */
#include "../../runtime/platform/player/host_queue.h"
#include "../../runtime/platform/player/host_hook.h"
#include "../../runtime/platform/player/queue_browser.h"
#include "../../runtime/platform/player/stock_info.h"
#include <stdatomic.h>
static atomic_int model_session=7,met_quit,queue_retains,queue_releases;
static pthread_t met_thread;
int xw_stock_info_bind(struct xw_stock_info *s){s->bound=1;s->owner=pthread_self();return 0;}
int xw_stock_info_session_key(struct xw_stock_info *s,struct xw_stock_session_key *out){assert(s->bound&&s->owner==pthread_self());out->list=1234;out->number=atomic_load(&model_session);return 0;}
int xw_stock_info_unbind(struct xw_stock_info *s){assert(s->owner==pthread_self());s->bound=0;return 0;}
int xw_stock_queue_owner_bind(struct xw_stock_queue_owner *s){assert(!s->bound);s->bound=1;s->owner=pthread_self();return 0;}
int xw_stock_queue_owner_session_matches(struct xw_stock_queue_owner *s,uint32_t session,uint32_t list,const struct xw_stock_session_key *key){assert(s->owner==pthread_self());uint32_t number=session==123?7:session==456?8:99;return list==key->list&&number==key->number?0:XW_PLAYER_STALE;}
int xw_stock_queue_owner_acquire(struct xw_stock_queue_owner *s,uint32_t session){assert(s->owner==pthread_self()&&!s->sequence&&(session==123||session==456));s->sequence=session;atomic_fetch_add(&queue_retains,1);return 0;}
int xw_stock_queue_owner_release(struct xw_stock_queue_owner *s){assert(s->sequence&&s->owner==pthread_self());s->sequence=0;atomic_fetch_add(&queue_releases,1);return 0;}
int xw_stock_queue_owner_unbind(struct xw_stock_queue_owner *s){assert(!s->sequence&&s->owner==pthread_self());s->bound=0;return 0;}
int xw_stock_queue_owner_cached_partial(struct xw_stock_queue_owner *s,uint32_t offset,uint32_t limit,struct xw_stock_queue_partial_page *out){
 assert(s->sequence);if(offset>4)return XW_PLAYER_INVALID;memset(out,0,sizeof *out);out->page.order.total=4;out->page.order.offset=offset;out->page.order.shuffled=1;out->page.order.count=4-offset<limit?4-offset:limit;
 const uint32_t map[4]={2,0,3,1};for(uint32_t i=0;i<out->page.order.count;i++)out->page.order.physical_indices[i]=map[offset+i];
 if(out->page.order.count){out->known_ids=1;assert(!xw_local_media_id_format(1,map[offset]+1+(s->sequence==456?10:0),&out->page.ids[0]));}return 0;
}
int xw_stock_queue_owner_query(struct xw_stock_queue_owner *s,struct xw_query_snapshot *out){memset(out,0,sizeof *out);out->domain=s->sequence==456;return 0;}
int xw_stock_media_adopt(struct xw_stock_media *s){assert(s->client&&s->gui_owner!=pthread_self());s->worker_set=1;s->worker=pthread_self();return 0;}
int xw_stock_media_snapshot_one(struct xw_stock_media *s,const struct xw_query_snapshot *q,uint32_t ordinal,struct xw_media_item *out){struct xw_media_id id;assert(!xw_local_media_id_format(1,ordinal+1+(q->domain?10:0),&id));return xw_stock_media_fetch(s,&id,out);}
static void *model_met(void *unused){(void)unused;while(!atomic_load(&met_quit)){xw_player_host_met_dispatch(999,7,4321);xw_player_host_met_dispatch(123,7,1234);xw_player_host_met_dispatch(456,7,1234);poll(0,0,1);}return 0;}
static void start_queue_model(void){assert(!pthread_create(&met_thread,0,model_met,0));int rc=XW_PLAYER_BUSY;for(int i=0;i<2000&&rc;i++){rc=xw_player_host_queue_attach(&broker);assert(!rc||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}assert(!rc);}
static void stop_queue_model(void){atomic_store(&met_quit,1);assert(!pthread_join(met_thread,0));assert(atomic_load(&queue_retains)>0&&atomic_load(&queue_retains)==atomic_load(&queue_releases));}

int xw_stock_queue_owner_group_plan(struct xw_stock_queue_owner *s,struct xw_stock_group_plan *p){(void)s;(void)p;return XW_PLAYER_UNSUPPORTED;}

int xw_stock_media_snapshot_page(struct xw_stock_media *s,const struct xw_query_snapshot *q,uint32_t offset,uint32_t limit,struct xw_stock_children_page *w,struct xw_stock_children_page *out){(void)s;(void)q;(void)offset;(void)limit;(void)w;(void)out;return XW_PLAYER_UNSUPPORTED;}
