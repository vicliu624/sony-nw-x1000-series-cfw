/* Actual host pthread job/cache lifecycle with modeled native media methods. */
#define _POSIX_C_SOURCE 200809L
#include "../../runtime/platform/player/metadata_async.h"
#include "../../runtime/platform/player/local_identity.h"
#include <pthread.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <poll.h>
typedef char mutex_fits[sizeof(pthread_mutex_t)<=64?1:-1];
typedef char condition_fits[sizeof(pthread_cond_t)<=64?1:-1];
typedef char attributes_fit[sizeof(pthread_attr_t)<=64?1:-1];
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition=PTHREAD_COND_INITIALIZER;
static unsigned opens,closes,fetches,live,block_fetch,fail_fetch;
static struct xw_metadata_async worker;
int xw_stock_media_source_ready(void){return 1;}
int xw_stock_media_open(struct xw_stock_media *s){pthread_mutex_lock(&gate);opens++;live++;pthread_mutex_unlock(&gate);memset(s,0,sizeof *s);s->client=1;s->bound=1;s->gui_owner=pthread_self();return 0;}
int xw_stock_media_fetch(struct xw_stock_media *s,const struct xw_media_id *id,struct xw_media_item *out){
 assert(s->client&&s->gui_owner!=pthread_self());s->worker=pthread_self();s->worker_set=1;
 struct xw_media_item unused;assert(xw_metadata_async_observe(&worker,id,7,1000,&unused)==XW_PLAYER_BUSY);
 pthread_mutex_lock(&gate);fetches++;pthread_cond_signal(&condition);while(block_fetch)pthread_cond_wait(&condition,&gate);unsigned fail=fail_fetch;pthread_mutex_unlock(&gate);
 if(fail)return XW_PLAYER_UNAVAILABLE;memset(out,0,sizeof *out);out->id=*id;strcpy(out->title,"Metadata 猫");out->flags=XW_MEDIA_TITLE_PRESENT;return 0;
}
int xw_stock_media_children(struct xw_stock_media *s,const struct xw_stock_children_query *q,struct xw_stock_children_page *out){
 assert(s->client&&s->gui_owner!=pthread_self());s->worker=pthread_self();s->worker_set=1;
 pthread_mutex_lock(&gate);fetches++;pthread_cond_signal(&condition);while(block_fetch)pthread_cond_wait(&condition,&gate);unsigned fail=fail_fetch;pthread_mutex_unlock(&gate);
 if(fail)return XW_PLAYER_IO;memset(out,0,sizeof *out);out->count=1;out->exhausted=1;
 assert(!xw_local_media_id_format(1,q->offset+1,&out->items[0].id));return 0;
}
int xw_stock_media_close(struct xw_stock_media *s){assert(s->client);assert(s->gui_owner==pthread_self()||(s->worker_set&&s->worker==pthread_self()));pthread_mutex_lock(&gate);assert(live);closes++;live--;pthread_mutex_unlock(&gate);memset(s,0,sizeof *s);return 0;}
static unsigned count_fetches(void){pthread_mutex_lock(&gate);unsigned n=fetches;pthread_mutex_unlock(&gate);return n;}
static void wait_fetch(unsigned n){for(unsigned i=0;i<2000&&count_fetches()<n;i++)poll(0,0,1);assert(count_fetches()>=n);}
static void release_fetch(void){pthread_mutex_lock(&gate);block_fetch=0;pthread_cond_broadcast(&condition);pthread_mutex_unlock(&gate);}
static int wait_result(const struct xw_media_id *id,uint64_t revision,unsigned long long now,struct xw_media_item *out){for(unsigned i=0;i<2000;i++){int rc=xw_metadata_async_observe(&worker,id,revision,now,out);if(!rc)return 0;assert(rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}return -1;}
int main(void){
 struct xw_media_id a,b;struct xw_media_item out,prior;assert(!xw_local_media_id_format(1,1,&a)&&!xw_local_media_id_format(1,2,&b));assert(!xw_metadata_async_init(&worker));
 memset(&out,0x5a,sizeof out);prior=out;block_fetch=1;
 assert(xw_metadata_async_observe(&worker,&a,7,1000,&out)==XW_PLAYER_UNAVAILABLE&&!memcmp(&out,&prior,sizeof out));wait_fetch(1);
 assert(xw_metadata_async_observe(&worker,&b,7,1001,&out)!=0&&!memcmp(&out,&prior,sizeof out));release_fetch();assert(!wait_result(&b,7,1001,&out));assert(!strcmp(out.id.value,b.value)&&!strcmp(out.title,"Metadata 猫"));
 pthread_mutex_lock(&gate);assert(opens==closes&&live==0);fail_fetch=1;unsigned before=fetches;pthread_mutex_unlock(&gate);
 assert(!xw_metadata_async_observe(&worker,&b,7,4000,&out));wait_fetch(before+1);
 for(unsigned i=0;i<2000;i++){int rc=xw_metadata_async_observe(&worker,&b,7,4000,&out);if(rc)break;poll(0,0,1);}assert(!worker.cache_valid);
 pthread_mutex_lock(&gate);fail_fetch=0;pthread_mutex_unlock(&gate);assert(!wait_result(&b,7,10000,&out));
 assert(xw_metadata_async_observe(&worker,&b,8,10001,&out)!=0);assert(!wait_result(&b,8,10001,&out));
 assert(xw_metadata_async_observe(&worker,0,0,10002,&out)!=0&&!worker.cache_valid);
 pthread_mutex_lock(&gate);block_fetch=1;before=fetches;pthread_mutex_unlock(&gate);
 assert(xw_metadata_async_observe(&worker,&a,9,11000,&out)!=0);wait_fetch(before+1);
 assert(xw_metadata_async_stop(&worker)==XW_PLAYER_ACCEPTED&&!xw_metadata_async_drained(&worker));assert(xw_metadata_async_destroy(&worker)==XW_PLAYER_BUSY);release_fetch();
 for(unsigned i=0;i<2000&&!xw_metadata_async_drained(&worker);i++)poll(0,0,1);
 assert(xw_metadata_async_drained(&worker)&&!xw_metadata_async_destroy(&worker));pthread_mutex_lock(&gate);assert(opens==closes&&live==0);pthread_mutex_unlock(&gate);
 static struct xw_children_async children;struct xw_stock_children_query query={0};struct xw_stock_children_page page,old;
 assert(!xw_children_async_init(&children));query.parent=a;query.limit=3;query.offset=4;
 memset(&page,0x5a,sizeof page);old=page;
 pthread_mutex_lock(&gate);block_fetch=1;before=fetches;pthread_mutex_unlock(&gate);
 assert(xw_children_async_observe(&children,&query,10,12000,&page)==XW_PLAYER_BUSY);wait_fetch(before+1);
 query.offset=8;assert(xw_children_async_observe(&children,&query,10,12001,&page)!=0&&!memcmp(&page,&old,sizeof page));release_fetch();
 int got=0;for(unsigned i=0;i<2000;i++){if(!xw_children_async_observe(&children,&query,10,12001,&page)){got=1;break;}poll(0,0,1);}assert(got&&page.count==1&&page.exhausted);
 struct xw_media_id wanted;assert(!xw_local_media_id_format(1,9,&wanted));assert(!strcmp(page.items[0].id.value,wanted.value));
 pthread_mutex_lock(&gate);before=fetches;pthread_mutex_unlock(&gate);query.kind=XW_STOCK_TRACKS;
 assert(xw_children_async_observe(&children,&query,10,12002,&page)!=0);
 got=0;for(unsigned i=0;i<2000;i++){if(!xw_children_async_observe(&children,&query,10,12002,&page)){got=1;break;}poll(0,0,1);}assert(got&&count_fetches()>before);
 old=page;pthread_mutex_lock(&gate);fail_fetch=1;pthread_mutex_unlock(&gate);
 int error=0;for(unsigned i=0;i<2000;i++){int rc=xw_children_async_observe(&children,&query,12,13000,&page);if(rc==XW_PLAYER_IO){error=1;break;}assert(rc!=0);poll(0,0,1);}assert(error&&!memcmp(&old,&page,sizeof page));
 pthread_mutex_lock(&gate);fail_fetch=0;pthread_mutex_unlock(&gate);
 got=0;for(unsigned i=0;i<2000;i++){if(!xw_children_async_observe(&children,&query,0,14000,&page)){got=1;break;}poll(0,0,1);}assert(got);
 pthread_mutex_lock(&gate);before=fetches;block_fetch=1;pthread_mutex_unlock(&gate);
 assert(xw_children_async_observe(&children,&query,0,17000,&page)!=0);wait_fetch(before+1);release_fetch();
 got=0;for(unsigned i=0;i<2000;i++){if(!xw_children_async_observe(&children,&query,0,17000,&page)){got=1;break;}poll(0,0,1);}assert(got);
 old=page;query.limit=0;assert(xw_children_async_observe(&children,&query,10,12002,&page)==XW_PLAYER_INVALID&&!memcmp(&old,&page,sizeof page));query.limit=3;
 assert(xw_children_async_observe(&children,0,0,12003,&page)!=0&&!children.worker.cache_valid);
 pthread_mutex_lock(&gate);block_fetch=1;before=fetches;pthread_mutex_unlock(&gate);
 assert(xw_children_async_observe(&children,&query,11,12004,&page)!=0);wait_fetch(before+1);
 assert(xw_metadata_async_stop(&children.worker)==XW_PLAYER_ACCEPTED&&!xw_metadata_async_drained(&children.worker));release_fetch();
 for(unsigned i=0;i<2000&&!xw_metadata_async_drained(&children.worker);i++)poll(0,0,1);
 assert(xw_metadata_async_drained(&children.worker)&&!xw_metadata_async_destroy(&children.worker));
 pthread_mutex_lock(&gate);assert(opens==closes&&live==0);pthread_mutex_unlock(&gate);
 puts("Async children: real worker, stale-page rejection, atomic output, invalid limits, revocation and nonblocking shutdown passed");
 puts("Async metadata: real threads, stale-ID/revision discard, cache refresh/failure, source revocation, nonblocking stop and balanced clients passed");return 0;
}
