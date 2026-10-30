#define _POSIX_C_SOURCE 200809L
#include "../../runtime/platform/player/player_broker.h"
#include "../../runtime/platform/player/local_identity.h"
#ifdef _WIN32
#include "windows_pthread.h"
#else
#include <pthread.h>
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#define poll xw_test_poll
#else
#include <poll.h>
#endif
static struct xw_player original;
static struct xw_player_broker broker;
static unsigned track=1,available=1,version=1,opened,closed,live,backend_closed;
static unsigned long long now=1000;
static unsigned clock_fail;
static pthread_mutex_t counters=PTHREAD_MUTEX_INITIALIZER;
int hb_monotonic_millis(unsigned long long *out){if(clock_fail)return -1;*out=now;return 0;}
int xw_stock_media_source_ready(void){return available!=0;}
int xw_stock_media_open(struct xw_stock_media *s){if(!available)return XW_PLAYER_UNAVAILABLE;memset(s,0,sizeof *s);s->client=1;s->bound=1;s->gui_owner=pthread_self();pthread_mutex_lock(&counters);opened++;live++;pthread_mutex_unlock(&counters);return 0;}
int xw_stock_media_fetch(struct xw_stock_media *s,const struct xw_media_id *id,struct xw_media_item *out){assert(pthread_self()!=s->gui_owner);s->worker_set=1;s->worker=pthread_self();poll(0,0,20);memset(out,0,sizeof *out);out->id=*id;uint32_t domain,number;assert(!xw_local_media_id_parse(id,&domain,&number));snprintf(out->title,sizeof out->title,"Song %u 猫",number);pthread_mutex_lock(&counters);unsigned v=version;pthread_mutex_unlock(&counters);snprintf(out->artist,sizeof out->artist,"Artist %u",v);out->flags=3;return 0;}
int xw_stock_media_children(struct xw_stock_media *s,const struct xw_stock_children_query *q,struct xw_stock_children_page *out){
 assert(s->client&&pthread_self()!=s->gui_owner&&q->kind>=XW_STOCK_TRACKS&&q->kind<=XW_STOCK_FORMAT3_CHILDREN);s->worker_set=1;s->worker=pthread_self();poll(0,0,20);memset(out,0,sizeof *out);
 if(q->kind==XW_STOCK_FORMAT3_LISTS){
  assert(!q->parent.value[0]);if(!q->offset){out->count=1;assert(!xw_local_media_id_format(1,99,&out->items[0].id));strcpy(out->items[0].title,"Modeled playlist");out->items[0].flags=XW_MEDIA_TITLE_PRESENT;}out->exhausted=1;return 0;
 }
 if(q->kind==XW_STOCK_FORMAT3_CHILDREN){struct xw_media_id expected;assert(!xw_local_media_id_format(1,99,&expected));if(strcmp(expected.value,q->parent.value))return XW_PLAYER_UNSUPPORTED;}
 else assert(!q->parent.value[0]);
 for(unsigned n=q->offset;n<3&&out->count<q->limit;n++){struct xw_media_item *item=&out->items[out->count++];assert(!xw_local_media_id_format(1,n+1,&item->id));snprintf(item->title,sizeof item->title,"Library %u",n+1);item->flags=XW_MEDIA_TITLE_PRESENT;}
 out->exhausted=q->offset+out->count>=3;return 0;
}
int xw_stock_media_close(struct xw_stock_media *s){assert(s->client);assert(pthread_self()==s->gui_owner||(s->worker_set&&pthread_self()==s->worker));pthread_mutex_lock(&counters);closed++;assert(live);live--;pthread_mutex_unlock(&counters);memset(s,0,sizeof *s);return 0;}
static int snapshot(void *ctx,struct xw_player_snapshot *out){(void)ctx;memset(out,0,sizeof *out);out->valid=XW_PF_TRACK|XW_PF_STATE|XW_PF_VOLUME;out->state=XW_PLAY_PAUSED;out->volume=12;out->volume_max=30;assert(!xw_local_media_id_format(1,track,&out->track.id));return 0;}
static int command(void *ctx,const struct xw_player_command *request){(void)ctx;if(request->operation==XW_OP_NEXT)track++;return XW_PLAYER_ACCEPTED;}
static int close_backend(void *ctx){(void)ctx;backend_closed++;return 0;}
static void wait_metadata(struct xw_player_snapshot *out,const char *title){for(unsigned i=0;i<2000;i++){assert(!xw_player_snapshot(&broker.player,out));if(out->valid&XW_PF_METADATA){assert(!strcmp(out->track.title,title));return;}poll(0,0,1);}assert(0);}
static unsigned queue_reads,queue_revokes,queue_closes,queue_revoke_busy;
static int queue_browse(void *context,const struct xw_media_query *q,uint64_t clock,struct xw_media_item *items,struct xw_media_page *page){
 assert(context==&queue_reads&&clock==now&&q->view==XW_MEDIA_QUEUE);queue_reads++;
 if(q->expected_revision)return XW_PLAYER_STALE;
 memset(items,0,sizeof *items);assert(!xw_local_media_id_format(1,42,&items->id));strcpy(items->title,"Queue song");items->flags=XW_MEDIA_TITLE_PRESENT;
 memset(page,0,sizeof *page);page->offset=q->offset;page->count=1;page->next_offset=q->offset+1;page->total=q->offset+1;return 0;
}
static int queue_revoke(void *context,uint64_t clock){assert(context==&queue_reads&&clock==(clock_fail?0:now));queue_revokes++;if(queue_revoke_busy){queue_revoke_busy=0;return XW_PLAYER_BUSY;}return 0;}
static int queue_close(void *context){assert(context==&queue_reads);return ++queue_closes==1?XW_PLAYER_BUSY:0;}
int main(void){
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_backend};assert(!xw_player_bind(&original,&provider)&&!xw_player_broker_bind(&broker,&original));
 struct xw_player_snapshot out;assert(!xw_player_snapshot(&broker.player,&out)&&!(out.valid&XW_PF_METADATA));
 struct xw_player_command next={0};next.operation=XW_OP_NEXT;assert(xw_player_command(&broker.player,&next)==XW_PLAYER_ACCEPTED);now++;
 wait_metadata(&out,"Song 2 猫");assert(!strcmp(out.track.artist,"Artist 1"));uint32_t changes;assert(!xw_player_poll(&broker.player,&out,&changes)&&(changes&XW_PC_METADATA));assert(!xw_player_poll(&broker.player,&out,&changes)&&!changes);
 pthread_mutex_lock(&counters);version=2;pthread_mutex_unlock(&counters);now=5000;
 for(unsigned i=0;i<2000;i++){assert(!xw_player_poll(&broker.player,&out,&changes));if(!strcmp(out.track.artist,"Artist 2")){assert(changes==XW_PC_METADATA);break;}poll(0,0,1);}assert(!strcmp(out.track.artist,"Artist 2"));
 available=0;xw_player_broker_tick(&broker,now);assert(!xw_player_poll(&broker.player,&out,&changes)&&!(out.valid&XW_PF_METADATA)&&changes==XW_PC_METADATA);
 available=1;now++;wait_metadata(&out,"Song 2 猫");assert(!strcmp(out.track.artist,"Artist 2"));
 assert(!xw_player_poll(&broker.player,&out,&changes)&&(out.valid&XW_PF_METADATA));
 pthread_mutex_lock(&counters);version=3;pthread_mutex_unlock(&counters);clock_fail=1;
 assert(!xw_player_poll(&broker.player,&out,&changes)&&!(out.valid&XW_PF_METADATA)&&(changes&XW_PC_METADATA));
 clock_fail=0;now++;
 assert(!xw_player_poll(&broker.player,&out,&changes)&&!(out.valid&XW_PF_METADATA));
 wait_metadata(&out,"Song 2 猫");assert(!strcmp(out.track.artist,"Artist 3"));
 assert(!xw_player_poll(&broker.player,&out,&changes)&&(changes&XW_PC_METADATA));
 struct xw_media_query query={0};query.view=XW_MEDIA_TRACKS;query.limit=2;
 struct xw_media_item rows[2],old_rows[2];struct xw_media_page page,old_page;
 memset(rows,0x5a,sizeof rows);memcpy(old_rows,rows,sizeof rows);memset(&page,0x5a,sizeof page);old_page=page;
 assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_BUSY&&!memcmp(rows,old_rows,sizeof rows)&&!memcmp(&page,&old_page,sizeof page));
 int ready=0;for(unsigned i=0;i<2000;i++){int result=xw_media_browse(&broker.player,&query,rows,2,&page);if(!result){ready=1;break;}assert(result==XW_PLAYER_BUSY);poll(0,0,1);}assert(ready&&page.revision==0&&page.count==2&&page.total==XW_MEDIA_TOTAL_UNKNOWN&&!strcmp(rows[0].title,"Library 1"));
 memcpy(old_rows,rows,sizeof rows);old_page=page;clock_fail=1;
 assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_UNAVAILABLE&&!memcmp(rows,old_rows,sizeof rows)&&!memcmp(&page,&old_page,sizeof page));clock_fail=0;now++;
 int after_clock=xw_media_browse(&broker.player,&query,rows,2,&page);assert(after_clock==XW_PLAYER_BUSY||after_clock==XW_PLAYER_UNAVAILABLE);
 ready=0;for(unsigned i=0;i<2000;i++){int result=xw_media_browse(&broker.player,&query,rows,2,&page);if(!result){ready=1;break;}assert(result==XW_PLAYER_BUSY||result==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}assert(ready&&page.count==2);
 memcpy(old_rows,rows,sizeof rows);old_page=page;query.expected_revision=7;
 assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_STALE&&!memcmp(rows,old_rows,sizeof rows)&&!memcmp(&page,&old_page,sizeof page));query.expected_revision=0;
 available=0;xw_player_broker_tick(&broker,now);assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_UNAVAILABLE&&!memcmp(rows,old_rows,sizeof rows));available=1;now++;
 query.offset=2;ready=0;for(unsigned i=0;i<2000;i++){int result=xw_media_browse(&broker.player,&query,rows,2,&page);if(!result){ready=1;break;}assert(result==XW_PLAYER_BUSY||result==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}assert(ready&&page.count==1&&page.next_offset==3&&!strcmp(rows[0].title,"Library 3"));
 query.view=XW_MEDIA_PLAYLISTS;query.offset=0;ready=0;
 for(unsigned i=0;i<2000;i++){int result=xw_media_browse(&broker.player,&query,rows,2,&page);if(!result){ready=1;break;}assert(result==XW_PLAYER_BUSY||result==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}assert(ready&&page.count==1&&!strcmp(rows[0].title,"Modeled playlist"));
 struct xw_media_id list=rows[0].id;query.view=XW_MEDIA_PLAYLIST_TRACKS;query.container=list;ready=0;
 for(unsigned i=0;i<2000;i++){int result=xw_media_browse(&broker.player,&query,rows,2,&page);if(!result){ready=1;break;}assert(result==XW_PLAYER_BUSY||result==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}assert(ready&&page.count==2&&!strcmp(rows[0].title,"Library 1"));
 memcpy(old_rows,rows,sizeof rows);old_page=page;assert(!xw_local_media_id_format(1,100,&query.container));int rejected=0;
 for(unsigned i=0;i<2000;i++){int result=xw_media_browse(&broker.player,&query,rows,2,&page);if(result==XW_PLAYER_UNSUPPORTED){rejected=1;break;}assert(result==XW_PLAYER_BUSY||result==XW_PLAYER_UNAVAILABLE);poll(0,0,1);}assert(rejected&&!memcmp(rows,old_rows,sizeof rows)&&!memcmp(&page,&old_page,sizeof page));
 query.view=XW_MEDIA_QUEUE;assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_UNSUPPORTED);
 memset(&query.container,0,sizeof query.container);query.offset=0;
 struct xw_player_queue_provider queue={&queue_reads,queue_browse,queue_revoke,queue_close};assert(!xw_player_broker_attach_queue(&broker,&queue));assert(xw_player_broker_attach_queue(&broker,&queue)==XW_PLAYER_BUSY);
 assert(!xw_media_browse(&broker.player,&query,rows,2,&page)&&page.count==1&&!strcmp(rows[0].title,"Queue song")&&queue_reads==1);
 memcpy(old_rows,rows,sizeof rows);old_page=page;query.expected_revision=1;assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_STALE&&!memcmp(rows,old_rows,sizeof rows)&&!memcmp(&page,&old_page,sizeof page));query.expected_revision=0;
 unsigned reads_before=queue_reads;available=0;xw_player_broker_tick(&broker,now);assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_UNAVAILABLE&&queue_reads==reads_before&&queue_revokes==2);available=1;
 available=0;queue_revoke_busy=1;xw_player_broker_tick(&broker,now);assert(broker.queue_revoke_pending);available=1;
 assert(!xw_media_browse(&broker.player,&query,rows,2,&page)&&!broker.queue_revoke_pending&&queue_revokes==4);
 memcpy(old_rows,rows,sizeof rows);old_page=page;unsigned before_clock_reads=queue_reads,before_clock_revokes=queue_revokes;clock_fail=1;
 assert(xw_media_browse(&broker.player,&query,rows,2,&page)==XW_PLAYER_UNAVAILABLE&&queue_reads==before_clock_reads&&queue_revokes==before_clock_revokes+1&&!memcmp(rows,old_rows,sizeof rows)&&!memcmp(&page,&old_page,sizeof page));clock_fail=0;now++;
 assert(!xw_media_browse(&broker.player,&query,rows,2,&page)&&queue_reads==before_clock_reads+1);
 assert(xw_player_close(&broker.player)==XW_PLAYER_BUSY&&broker.backend==&original&&original.initialized&&!backend_closed);
 int rc=XW_PLAYER_BUSY;for(unsigned i=0;i<2000&&rc==XW_PLAYER_BUSY;i++){rc=xw_player_close(&broker.player);if(rc==XW_PLAYER_BUSY)poll(0,0,1);}assert(!rc&&original.initialized&&!backend_closed&&queue_closes==2);
 pthread_mutex_lock(&counters);assert(opened==closed&&!live);pthread_mutex_unlock(&counters);assert(!xw_player_close(&original)&&backend_closed==1);
 puts("Broker: background metadata, stale-track discard, periodic text changes, source-off invalidation and original-player preservation passed");return 0;
}
