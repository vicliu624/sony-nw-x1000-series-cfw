/* Generic ARM-kernel fixture; original Sony LinuxThreads, no device APIs. */
#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/source_intent.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *,const void *);
extern int pthread_mutex_lock(void *);
extern int pthread_mutex_unlock(void *);
extern int pthread_mutex_destroy(void *);
static union xw_pthread_storage gate;
static unsigned available=1,hold=1,entered,opened,closed,submissions;
static unsigned long owner;
static uint64_t now=100;
static struct xw_source_intent intent;
static struct xw_stock_gui gui;
static struct xw_stock_source_result receipt;
static unsigned read_counter(unsigned *value){assert(!pthread_mutex_lock(&gate));unsigned n=*value;assert(!pthread_mutex_unlock(&gate));return n;}
static void set_counter(unsigned *value,unsigned n){assert(!pthread_mutex_lock(&gate));*value=n;assert(!pthread_mutex_unlock(&gate));}
int xw_stock_media_source_ready(void){assert(pthread_self()==owner);return read_counter(&available);}
int xw_stock_media_open(struct xw_stock_media *s){
 assert(pthread_self()==owner);memset(s,0,sizeof *s);s->bound=1;s->gui_owner=owner;
 assert(!pthread_mutex_lock(&gate));opened++;assert(!pthread_mutex_unlock(&gate));return 0;
}
int xw_stock_media_validate_audio(struct xw_stock_media *s,const struct xw_media_id *id,struct xw_stock_audio_identity *out){
 assert(s->bound&&pthread_self()!=owner);s->worker=pthread_self();s->worker_set=1;
 struct xw_stock_source_result ignored;assert(xw_source_intent_observe(&intent,id,99,0,&ignored)==XW_PLAYER_BUSY);
 assert(!pthread_mutex_lock(&gate));entered++;assert(!pthread_mutex_unlock(&gate));
 while(read_counter(&hold))usleep(1000);
 uint32_t domain,number;assert(!xw_local_media_id_parse(id,&domain,&number));if(number==3)return XW_PLAYER_UNSUPPORTED;
 memset(out,0,sizeof *out);out->id=*id;out->media_type=1;return 0;
}
int xw_stock_media_close(struct xw_stock_media *s){
 assert(s->bound&&(s->gui_owner==pthread_self()||(s->worker_set&&s->worker==pthread_self())));s->bound=0;
 assert(!pthread_mutex_lock(&gate));closed++;assert(!pthread_mutex_unlock(&gate));return 0;
}
int xw_stock_media_fetch(struct xw_stock_media *s,const struct xw_media_id *id,struct xw_media_item *out){(void)s;(void)id;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_stock_media_children(struct xw_stock_media *s,const struct xw_stock_children_query *q,struct xw_stock_children_page *out){(void)s;(void)q;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_stock_gui_read(struct xw_stock_gui *g,struct xw_stock_gui_view *out){assert(g==&gui&&pthread_self()==owner);memset(out,0,sizeof *out);out->active=1;out->mode=1;out->state=5;return 0;}
int xw_stock_source_submit(struct xw_stock_gui *g,const struct xw_media_id *id,struct xw_stock_source_result *out){
 assert(g==&gui&&id->value[0]&&pthread_self()==owner);assert(read_counter(&opened)==read_counter(&closed));
 submissions++;out->attempted=out->moved=1;out->ticket=77;return XW_PLAYER_UNCERTAIN;
}
int xw_player_snapshot(struct xw_player *p,struct xw_player_snapshot *out){(void)p;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
static int observe(const struct xw_media_id *id,uint64_t generation){return xw_source_intent_observe(&intent,id,generation,now++,&receipt);}
static void wait_entered(unsigned n){for(unsigned i=0;i<2000&&read_counter(&entered)<n;i++)usleep(1000);assert(read_counter(&entered)>=n);}
static int wait_result(const struct xw_media_id *id,uint64_t generation){for(unsigned i=0;i<2000;i++){int rc=observe(id,generation);if(rc!=XW_PLAYER_BUSY&&rc!=XW_PLAYER_UNAVAILABLE)return rc;usleep(1000);}assert(0);return 0;}
int main(void){
 owner=pthread_self();assert(!pthread_mutex_init(&gate,0));
 struct xw_media_id a,b,video;assert(!xw_local_media_id_format(1,1,&a));assert(!xw_local_media_id_format(1,2,&b));assert(!xw_local_media_id_format(1,3,&video));
 assert(!xw_source_intent_init(&intent,&gui));assert(observe(&a,1)==XW_PLAYER_BUSY);wait_entered(1);
 assert(observe(&b,2)==XW_PLAYER_UNAVAILABLE&&!submissions);set_counter(&hold,0);
 assert(wait_result(&b,2)==XW_PLAYER_UNCERTAIN&&submissions==1);
 assert(observe(&b,2)==XW_PLAYER_UNCERTAIN&&submissions==1);
 puts("PLAYER_ORIGINAL_THREAD_REPLACEMENT_PASS");fflush(stdout);
 set_counter(&hold,1);unsigned n=read_counter(&entered);assert(observe(&a,3)==XW_PLAYER_BUSY);wait_entered(n+1);
 assert(!observe(0,0));set_counter(&hold,0);assert(observe(&a,3)==XW_PLAYER_STALE&&submissions==1);
 assert(wait_result(&video,4)==XW_PLAYER_UNSUPPORTED&&submissions==1);
 set_counter(&hold,1);n=read_counter(&entered);assert(observe(&a,5)==XW_PLAYER_BUSY);wait_entered(n+1);
 set_counter(&available,0);assert(observe(&a,5)==XW_PLAYER_UNAVAILABLE);set_counter(&hold,0);set_counter(&available,1);
 assert(observe(&a,5)==XW_PLAYER_UNAVAILABLE&&submissions==1);assert(wait_result(&b,6)==XW_PLAYER_UNCERTAIN&&submissions==2);
 assert(xw_metadata_async_stop(&intent.check.worker)==XW_PLAYER_ACCEPTED);
 for(unsigned i=0;i<2000&&!xw_metadata_async_drained(&intent.check.worker);i++)usleep(1000);
 assert(xw_metadata_async_drained(&intent.check.worker));assert(!xw_metadata_async_destroy(&intent.check.worker));
 assert(read_counter(&opened)==read_counter(&closed));assert(observe(&b,6)==XW_PLAYER_CLOSED);assert(!pthread_mutex_destroy(&gate));
 puts("PLAYER_ORIGINAL_THREADS_PASS");fflush(stdout);return 0;
}
