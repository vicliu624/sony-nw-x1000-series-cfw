#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/audio_check_async.h"
#include "../../runtime/platform/player/local_identity.h"
#ifdef _WIN32
#include "windows_pthread.h"
#else
#include <pthread.h>
#include <unistd.h>
#endif
#include <stdatomic.h>
#include <assert.h>
#include <string.h>
static atomic_int available=1,release_read,entered,opened,closed;
static struct xw_audio_check_async check;
static struct xw_stock_audio_identity result,before;
static struct xw_media_id a,b,video;
static uint64_t now=100;
static unsigned long gui;
int xw_stock_media_source_ready(void){assert(pthread_self()==gui);return atomic_load(&available);}
int xw_stock_media_open(struct xw_stock_media *m){memset(m,0,sizeof *m);m->bound=1;m->gui_owner=pthread_self();atomic_fetch_add(&opened,1);return 0;}
int xw_stock_media_validate_audio(struct xw_stock_media *m,const struct xw_media_id *id,struct xw_stock_audio_identity *out){
 assert(m->bound&&m->gui_owner!=pthread_self());struct xw_stock_audio_identity ignored;assert(xw_audio_check_async_observe(&check,id,99,0,&ignored)==XW_PLAYER_BUSY);m->worker_set=1;m->worker=pthread_self();atomic_fetch_add(&entered,1);while(!atomic_load(&release_read))usleep(1000);
 uint32_t d,n;assert(!xw_local_media_id_parse(id,&d,&n));if(n==3)return XW_PLAYER_UNSUPPORTED;assert(!xw_local_media_id_format(d,n,&out->id));out->object_type=0;out->media_type=1;return 0;
}
int xw_stock_media_close(struct xw_stock_media *m){assert(m->bound&&(m->gui_owner==pthread_self()||(m->worker_set&&m->worker==pthread_self())));m->bound=0;atomic_fetch_add(&closed,1);return 0;}
int xw_stock_media_fetch(struct xw_stock_media *m,const struct xw_media_id *id,struct xw_media_item *out){(void)m;(void)id;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_stock_media_children(struct xw_stock_media *m,const struct xw_stock_children_query *q,struct xw_stock_children_page *p){(void)m;(void)q;(void)p;assert(0);return XW_PLAYER_PROTOCOL;}
static int observe(const struct xw_media_id *id,uint64_t generation){return xw_audio_check_async_observe(&check,id,generation,now++,&result);}
static void wait_entered(int target){for(unsigned i=0;i<5000&&atomic_load(&entered)<target;i++)usleep(1000);assert(atomic_load(&entered)>=target);}
static int wait_result(const struct xw_media_id *id,uint64_t gen){int rc=XW_PLAYER_BUSY;for(unsigned i=0;i<5000;i++){rc=observe(id,gen);if(rc!=XW_PLAYER_BUSY&&rc!=XW_PLAYER_UNAVAILABLE)return rc;usleep(1000);}assert(0);return rc;}
int main(void){gui=pthread_self();assert(!xw_local_media_id_format(1,1,&a)&&!xw_local_media_id_format(1,2,&b)&&!xw_local_media_id_format(1,3,&video));assert(!xw_audio_check_async_init(&check));memset(&result,0x5a,sizeof result);before=result;
 assert(observe(&a,0)==XW_PLAYER_INVALID&&atomic_load(&opened)==0);assert(observe(&a,1)==XW_PLAYER_BUSY);wait_entered(1);
 assert(observe(&b,2)==XW_PLAYER_UNAVAILABLE&&!memcmp(&result,&before,sizeof result));atomic_store(&release_read,1);
 assert(!wait_result(&b,2)&&!strcmp(result.id.value,b.value)&&result.object_type==0&&result.media_type==1);assert(atomic_load(&opened)==atomic_load(&closed));
 struct xw_media_id tailed=b;tailed.value[64]='x';int before_tail=atomic_load(&entered);assert(!observe(&tailed,2)&&atomic_load(&entered)==before_tail);
 before=result;assert(wait_result(&video,3)==XW_PLAYER_UNSUPPORTED&&!memcmp(&result,&before,sizeof result));
 assert(!wait_result(&b,4));int queries=atomic_load(&entered);assert(observe(&b,5)==XW_PLAYER_BUSY);assert(!wait_result(&b,5)&&atomic_load(&entered)>queries);
 before=result;atomic_store(&available,0);queries=atomic_load(&entered);assert(observe(&b,5)==XW_PLAYER_UNAVAILABLE&&!memcmp(&result,&before,sizeof result)&&atomic_load(&entered)==queries);atomic_store(&available,1);assert(observe(&b,5)==XW_PLAYER_BUSY);assert(!wait_result(&b,5));
 atomic_store(&release_read,0);queries=atomic_load(&entered);assert(observe(&a,6)==XW_PLAYER_BUSY);wait_entered(queries+1);before=result;assert(observe(0,0)==XW_PLAYER_UNAVAILABLE&&!memcmp(&result,&before,sizeof result));
 assert(xw_metadata_async_stop(&check.worker)==XW_PLAYER_ACCEPTED);assert(!xw_metadata_async_drained(&check.worker));atomic_store(&release_read,1);
 for(unsigned i=0;i<5000&&!xw_metadata_async_drained(&check.worker);i++)usleep(1000);assert(xw_metadata_async_drained(&check.worker)&&!xw_metadata_async_destroy(&check.worker));assert(atomic_load(&opened)==atomic_load(&closed));assert(observe(&b,7)==XW_PLAYER_CLOSED);return 0;}
