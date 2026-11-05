#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/source_intent.h"
#include "../../runtime/platform/player/local_identity.h"
#ifdef _WIN32
#include "windows_pthread.h"
#else
#include <pthread.h>
#include <unistd.h>
#endif
#ifdef XW_TEST_PTHREAD_ATOMICS
typedef int atomic_int;
static union xw_pthread_storage atomic_guard;
static int atomic_load(const atomic_int *p){pthread_mutex_lock((void *)&atomic_guard);int value=*p;pthread_mutex_unlock((void *)&atomic_guard);return value;}
static void atomic_store(atomic_int *p,int value){pthread_mutex_lock((void *)&atomic_guard);*p=value;pthread_mutex_unlock((void *)&atomic_guard);}
static int atomic_fetch_add(atomic_int *p,int value){pthread_mutex_lock((void *)&atomic_guard);int before=*p;*p+=value;pthread_mutex_unlock((void *)&atomic_guard);return before;}
#else
#include <stdatomic.h>
#endif
#include <assert.h>
#include <string.h>
static atomic_int available=1,release_read,entered,opened,closed;
static unsigned submissions;
static unsigned long owner;
static uint64_t now=100;
static struct xw_source_intent intent;
static struct xw_source_intent *tested_intent=&intent;
static struct xw_stock_gui gui;
static struct xw_stock_source_result receipt;
#ifndef XW_ASYNC_MANAGED_FIXTURE
int xw_player_snapshot(struct xw_player *p,struct xw_player_snapshot *out){(void)p;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
#endif
int xw_stock_media_source_ready(void){assert(pthread_self()==owner);return atomic_load(&available);}
int xw_stock_media_open(struct xw_stock_media *m){memset(m,0,sizeof *m);m->bound=1;m->gui_owner=pthread_self();atomic_fetch_add(&opened,1);return 0;}
int xw_stock_media_validate_audio(struct xw_stock_media *m,const struct xw_media_id *id,struct xw_stock_audio_identity *out){
 assert(m->bound&&m->gui_owner!=pthread_self());m->worker_set=1;m->worker=pthread_self();
 struct xw_stock_source_result ignored;assert(xw_source_intent_observe(tested_intent,id,100,0,&ignored)==XW_PLAYER_BUSY);
 atomic_fetch_add(&entered,1);while(!atomic_load(&release_read))usleep(1000);
 uint32_t d,n;assert(!xw_local_media_id_parse(id,&d,&n));if(n==3)return XW_PLAYER_UNSUPPORTED;
 memset(out,0,sizeof *out);out->id=*id;out->media_type=1;return 0;
}
int xw_stock_media_close(struct xw_stock_media *m){assert(m->bound&&(m->gui_owner==pthread_self()||(m->worker_set&&m->worker==pthread_self())));m->bound=0;atomic_fetch_add(&closed,1);return 0;}
int xw_stock_media_fetch(struct xw_stock_media *m,const struct xw_media_id *id,struct xw_media_item *out){(void)m;(void)id;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_stock_media_children(struct xw_stock_media *m,const struct xw_stock_children_query *q,struct xw_stock_children_page *p){(void)m;(void)q;(void)p;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_stock_gui_read(struct xw_stock_gui *g,struct xw_stock_gui_view *v){assert(pthread_self()==owner&&g==&gui);memset(v,0,sizeof *v);v->active=1;v->mode=1;v->state=5;return 0;}
int xw_stock_source_submit(struct xw_stock_gui *g,const struct xw_media_id *id,struct xw_stock_source_result *r){
 assert(pthread_self()==owner&&g==&gui&&id->value[0]);assert(atomic_load(&opened)==atomic_load(&closed));
 submissions++;r->attempted=r->moved=1;r->ticket=77;return XW_PLAYER_UNCERTAIN;
}
static int observe(const struct xw_media_id *id,uint64_t generation){return xw_source_intent_observe(&intent,id,generation,now++,&receipt);}
static void wait_entered(int n){for(unsigned i=0;i<5000&&atomic_load(&entered)<n;i++)usleep(1000);assert(atomic_load(&entered)>=n);}
static int wait_result(const struct xw_media_id *id,uint64_t generation){for(unsigned i=0;i<5000;i++){int rc=observe(id,generation);if(rc!=XW_PLAYER_BUSY&&rc!=XW_PLAYER_UNAVAILABLE)return rc;usleep(1000);}assert(0);return 0;}
int main(void){
 owner=pthread_self();struct xw_media_id a={{0}},b={{0}},video={{0}};
 assert(!xw_local_media_id_format(1,1,&a));assert(!xw_local_media_id_format(1,2,&b));assert(!xw_local_media_id_format(1,3,&video));
 assert(!xw_source_intent_init(&intent,&gui));assert(observe(&a,1)==XW_PLAYER_BUSY);wait_entered(1);
 assert(observe(&b,2)==XW_PLAYER_UNAVAILABLE&&!submissions);atomic_store(&release_read,1);
 assert(wait_result(&b,2)==XW_PLAYER_UNCERTAIN&&submissions==1);assert(observe(&b,2)==XW_PLAYER_UNCERTAIN&&submissions==1);
 atomic_store(&release_read,0);int n=atomic_load(&entered);assert(observe(&a,3)==XW_PLAYER_BUSY);wait_entered(n+1);
 assert(!observe(0,0));atomic_store(&release_read,1);assert(observe(&a,3)==XW_PLAYER_STALE&&submissions==1);
 assert(wait_result(&video,4)==XW_PLAYER_UNSUPPORTED&&submissions==1);
 atomic_store(&release_read,0);n=atomic_load(&entered);assert(observe(&a,5)==XW_PLAYER_BUSY);wait_entered(n+1);
 atomic_store(&available,0);assert(observe(&a,5)==XW_PLAYER_UNAVAILABLE);atomic_store(&release_read,1);atomic_store(&available,1);
 assert(observe(&a,5)==XW_PLAYER_UNAVAILABLE&&submissions==1);
 assert(wait_result(&b,6)==XW_PLAYER_UNCERTAIN&&submissions==2);
 assert(xw_metadata_async_stop(&intent.check.worker)==XW_PLAYER_ACCEPTED);
 for(unsigned i=0;i<5000&&!xw_metadata_async_drained(&intent.check.worker);i++)usleep(1000);
 assert(xw_metadata_async_drained(&intent.check.worker));assert(!xw_metadata_async_destroy(&intent.check.worker));
 assert(atomic_load(&opened)==atomic_load(&closed));assert(observe(&b,6)==XW_PLAYER_CLOSED);return 0;
}
