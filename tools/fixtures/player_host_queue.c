#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/host_queue.h"
#include "../../runtime/platform/player/host_hook.h"
#include "../../runtime/platform/player/queue_browser.h"
#include "../../runtime/platform/player/stock_info.h"
#include <pthread.h>
#include <stdatomic.h>
#include <assert.h>
#include <string.h>
#include <unistd.h>
static pthread_t gui;
static struct xw_player_queue_provider attached;
static atomic_int captures,unbinds,quitting,closed,other_seen,captures_other;
static atomic_int gui_list=1234;
static unsigned browser_live,close_attempts;
int xw_player_broker_attach_queue(struct xw_player_broker *b,const struct xw_player_queue_provider *p){(void)b;assert(pthread_self()==gui);attached=*p;return 0;}
int xw_queue_browser_init(struct xw_queue_browser *b){(void)b;assert(pthread_self()==gui&&!browser_live);browser_live=1;return 0;}
int xw_queue_browser_capture(struct xw_queue_browser *b,struct xw_stock_queue_owner *o,uint32_t session){(void)b;assert(pthread_self()!=gui&&o->bound&&(session==123||session==456)&&browser_live&&!atomic_load(&closed));if(session==123)atomic_fetch_add(&captures,1);else atomic_fetch_add(&captures_other,1);return 0;}
int xw_queue_browser_browse(struct xw_queue_browser *b,const struct xw_media_query *q,uint64_t now,struct xw_media_item *items,struct xw_media_page *page){(void)b;(void)q;(void)now;(void)items;(void)page;assert(pthread_self()==gui&&browser_live);return XW_PLAYER_BUSY;}
int xw_queue_browser_revoke(struct xw_queue_browser *b,uint64_t now){(void)b;(void)now;assert(pthread_self()==gui&&browser_live);return 0;}
int xw_queue_browser_close(struct xw_queue_browser *b){(void)b;assert(pthread_self()==gui&&atomic_load(&unbinds)==3&&browser_live);if(++close_attempts==1)return XW_PLAYER_BUSY;browser_live=0;atomic_store(&closed,1);return 0;}
int xw_stock_queue_owner_bind(struct xw_stock_queue_owner *o){assert(pthread_self()!=gui&&!o->bound);o->bound=1;o->owner=pthread_self();return 0;}
int xw_stock_queue_owner_unbind(struct xw_stock_queue_owner *o){assert(o->bound&&o->owner==pthread_self());o->bound=0;atomic_fetch_add(&unbinds,1);return 0;}
int xw_stock_info_bind(struct xw_stock_info *s){assert(pthread_self()==gui);s->bound=1;return 0;}
int xw_stock_info_session_key(struct xw_stock_info *s,struct xw_stock_session_key *out){assert(pthread_self()==gui&&s->bound);out->list=atomic_load(&gui_list);out->number=out->list==1234?7:8;return 0;}
int xw_stock_info_unbind(struct xw_stock_info *s){assert(pthread_self()==gui);s->bound=0;return 0;}
int xw_stock_queue_owner_session_matches(struct xw_stock_queue_owner *s,uint32_t session,uint32_t list,const struct xw_stock_session_key *key){assert(pthread_self()!=gui&&s->bound&&s->owner==pthread_self());return list==key->list&&((session==123&&key->number==7)||(session==456&&key->number==8))?0:XW_PLAYER_STALE;}
static void *met(void *p){(void)p;while(!atomic_load(&quitting)){xw_player_host_met_dispatch(999,7,1234);xw_player_host_met_dispatch(123,7,1234);usleep(1000);}return 0;}
static void *other_met(void *p){(void)p;while(!atomic_load(&quitting)){xw_player_host_met_dispatch(999,7,4321);xw_player_host_met_dispatch(456,7,4321);atomic_store(&other_seen,1);usleep(1000);}return 0;}
int main(void){gui=pthread_self();struct xw_player_broker b={0};assert(xw_player_host_queue_attach(&b)==XW_PLAYER_UNAVAILABLE);
 pthread_t t,other;assert(!pthread_create(&other,0,other_met,0));while(!atomic_load(&other_seen))usleep(1000);int rc=XW_PLAYER_UNAVAILABLE;
 for(int i=0;i<5000&&rc;i++){rc=xw_player_host_queue_attach(&b);assert(!rc||rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE);usleep(1000);}assert(!rc&&attached.context);assert(!pthread_create(&t,0,met,0));
 for(int i=0;i<5000&&!atomic_load(&captures);i++)usleep(1000);assert(atomic_load(&captures)>0);
 struct xw_media_query query={0};query.view=XW_MEDIA_QUEUE;query.limit=1;struct xw_media_item row;struct xw_media_page page;
 atomic_store(&gui_list,4321);
 for(int i=0;i<5000&&!atomic_load(&captures_other);i++){assert(attached.browse(attached.context,&query,2,&row,&page)==XW_PLAYER_BUSY);usleep(1000);}assert(atomic_load(&captures_other)>0);
 int prior=atomic_load(&captures);atomic_store(&gui_list,1234);
 for(int i=0;i<5000&&atomic_load(&captures)==prior;i++){assert(attached.browse(attached.context,&query,3,&row,&page)==XW_PLAYER_BUSY);usleep(1000);}assert(atomic_load(&captures)>prior);
 do{rc=attached.revoke(attached.context,1);}while(rc==XW_PLAYER_BUSY);assert(!rc);
 rc=attached.close(attached.context);assert(rc==XW_PLAYER_BUSY);
 for(int i=0;i<5000&&rc;i++){rc=attached.close(attached.context);assert(!rc||rc==XW_PLAYER_BUSY);usleep(1000);}assert(!rc&&close_attempts==2&&atomic_load(&unbinds)==3);
 int count=atomic_load(&captures);usleep(10000);assert(count==atomic_load(&captures));assert(xw_player_host_queue_attach(&b)==XW_PLAYER_CLOSED);
 atomic_store(&quitting,1);assert(!pthread_join(t,0));assert(!pthread_join(other,0));return 0;}
