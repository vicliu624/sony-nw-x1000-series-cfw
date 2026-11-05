#include "../../runtime/platform/player/source_intent.h"
#include "../../runtime/platform/player/local_identity.h"
#include "../../runtime/platform/player/provider.h"
#include <assert.h>
#include <string.h>
static unsigned long thread=1;
static unsigned ready=1,active=1,phase=5,reads,submits,attempts,revokes;
static int validation=XW_PLAYER_BUSY,submit_result=XW_PLAYER_ACCEPTED,attempt=1;
static struct xw_source_intent intent;
static struct xw_stock_gui gui;
static struct xw_stock_source_result out;
static struct xw_player_snapshot snapshot;
static int snapshot_result;
static unsigned snapshot_reads;
static struct xw_player backend_instance;
int xw_player_snapshot(struct xw_player *p,struct xw_player_snapshot *out){assert(p);snapshot_reads++;if(snapshot_result)return snapshot_result;*out=snapshot;return 0;}
unsigned long pthread_self(void){return thread;}
int xw_audio_check_async_init(struct xw_audio_check_async *s){s->worker.initialized=1;s->worker.owner=thread;return 0;}
int xw_audio_check_async_observe(struct xw_audio_check_async *s,const struct xw_media_id *id,uint64_t generation,uint64_t now,struct xw_stock_audio_identity *result){
 (void)s;(void)now;if(!id){revokes++;return XW_PLAYER_UNAVAILABLE;}assert(generation);reads++;
 if(validation)return validation;memset(result,0,sizeof *result);result->id=*id;result->media_type=1;return 0;
}
int xw_stock_media_source_ready(void){assert(thread==1);return ready;}
int xw_stock_gui_read(struct xw_stock_gui *g,struct xw_stock_gui_view *v){assert(g==&gui&&thread==1);memset(v,0,sizeof *v);v->mode=1;v->state=phase;v->active=active;return 0;}
int xw_stock_source_submit(struct xw_stock_gui *g,const struct xw_media_id *id,struct xw_stock_source_result *r){
 assert(g==&gui&&thread==1&&id->value[0]);submits++;r->attempted=attempt;r->moved=attempt;r->ticket=attempt?77:UINT32_MAX;attempts+=attempt;return submit_result;
}
static int observe(const struct xw_media_id *id,uint64_t generation,uint64_t now){return xw_source_intent_observe(&intent,id,generation,now,&out);}
int main(void){
 struct xw_media_id a={{0}},b={{0}};assert(!xw_local_media_id_format(1,1,&a));assert(!xw_local_media_id_format(1,2,&b));
 assert(!xw_source_intent_init(&intent,&gui));assert(xw_source_intent_init(&intent,&gui)==XW_PLAYER_BUSY);
 memset(&out,0x5a,sizeof out);struct xw_stock_source_result prior=out;
 assert(observe(&a,0,1)==XW_PLAYER_INVALID&&!memcmp(&out,&prior,sizeof out)&&!reads);
 assert(observe(&a,1,1)==XW_PLAYER_BUSY&&!attempts&&!memcmp(&out,&prior,sizeof out));
 struct xw_player *backend=&backend_instance;
 assert(xw_source_intent_check_target(&intent,backend,1)==XW_PLAYER_BUSY&&!snapshot_reads);
 validation=0;assert(observe(&b,2,2)==XW_PLAYER_ACCEPTED&&attempts==1&&out.moved&&out.ticket==77);
 assert(xw_source_intent_check_target(&intent,backend,1)==XW_PLAYER_STALE&&!snapshot_reads);
 assert(xw_source_intent_check_target(&intent,backend,2)==XW_PLAYER_UNAVAILABLE);
 snapshot.valid=XW_PF_TRACK|XW_PF_STATE;snapshot.track.id=b;snapshot.state=XW_PLAY_PAUSED;
 assert(xw_source_intent_check_target(&intent,backend,2)==XW_PLAYER_BUSY);
 snapshot.state=XW_PLAY_PLAYING;snapshot.track.id=a;assert(xw_source_intent_check_target(&intent,backend,2)==XW_PLAYER_BUSY);
 snapshot.track.id=b;assert(!xw_source_intent_check_target(&intent,backend,2));
 snapshot.state=XW_PLAY_UNKNOWN;assert(xw_source_intent_check_target(&intent,backend,2)==XW_PLAYER_UNAVAILABLE);
 snapshot_result=XW_PLAYER_IO;assert(xw_source_intent_check_target(&intent,backend,2)==XW_PLAYER_IO);snapshot_result=0;
 snapshot.state=XW_PLAY_PAUSED;assert(xw_source_intent_check_target(&intent,backend,2)==XW_PLAYER_BUSY); /* no sticky success */
 unsigned before=reads;ready=0;assert(observe(&b,2,3)==XW_PLAYER_ACCEPTED&&attempts==1&&reads==before);ready=1;
 struct xw_media_id tailed=b;tailed.value[64]='x';assert(observe(&tailed,2,3)==XW_PLAYER_ACCEPTED&&attempts==1);
 assert(observe(&a,2,3)==XW_PLAYER_INVALID&&attempts==1);
 validation=XW_PLAYER_BUSY;assert(observe(&a,3,4)==XW_PLAYER_BUSY);prior=out;
 assert(!observe(0,0,5)&&!memcmp(&out,&prior,sizeof out));validation=0;
 assert(observe(&a,3,6)==XW_PLAYER_STALE&&attempts==1);assert(observe(&b,2,6)==XW_PLAYER_STALE);
 validation=XW_PLAYER_UNSUPPORTED;assert(observe(&a,4,7)==XW_PLAYER_UNSUPPORTED&&!out.attempted);
 before=reads;assert(observe(&a,4,8)==XW_PLAYER_UNSUPPORTED&&reads==before&&attempts==1);
 validation=0;submit_result=XW_PLAYER_UNCERTAIN;assert(observe(&b,5,9)==XW_PLAYER_UNCERTAIN&&attempts==2&&out.moved);
 assert(observe(&b,5,10)==XW_PLAYER_UNCERTAIN&&attempts==2);
 snapshot.state=XW_PLAY_PLAYING;snapshot.track.id=b;assert(!xw_source_intent_check_target(&intent,backend,5));
 intent.result=0;assert(xw_source_intent_check_target(&intent,backend,5)==XW_PLAYER_PROTOCOL);intent.result=XW_PLAYER_UNCERTAIN;
 attempt=0;submit_result=XW_PLAYER_BUSY;prior=out;assert(observe(&a,6,11)==XW_PLAYER_BUSY&&!memcmp(&out,&prior,sizeof out)&&attempts==2);
 attempt=1;submit_result=XW_PLAYER_ACCEPTED;assert(observe(&a,6,12)==XW_PLAYER_ACCEPTED&&attempts==3);
 validation=XW_PLAYER_BUSY;assert(observe(&a,7,13)==XW_PLAYER_BUSY);ready=0;
 assert(observe(&a,7,14)==XW_PLAYER_UNAVAILABLE&&!out.attempted);ready=1;validation=0;
 assert(observe(&a,7,15)==XW_PLAYER_UNAVAILABLE&&attempts==3);
 assert(observe(&a,8,12)==XW_PLAYER_STALE&&attempts==3);assert(observe(&a,8,16)==XW_PLAYER_STALE);
 thread=2;before=reads;assert(observe(&b,9,17)==XW_PLAYER_BUSY&&reads==before);thread=1;
 active=0;assert(observe(&b,9,17)==XW_PLAYER_UNAVAILABLE&&reads==before);active=1;
 phase=4;assert(observe(&b,9,18)==XW_PLAYER_BUSY&&reads==before);phase=5;
 assert(observe(&b,9,19)==XW_PLAYER_ACCEPTED&&attempts==4);
 assert(xw_source_intent_observe(&intent,&a,10,20,(struct xw_stock_source_result *)&a)==XW_PLAYER_INVALID);
 assert(observe(&a,UINT64_MAX,21)==XW_PLAYER_ACCEPTED&&attempts==5);
 assert(observe(&a,0,22)==XW_PLAYER_INVALID&&observe(&b,9,22)==XW_PLAYER_STALE&&attempts==5);
 intent.check.worker.initialized=0;assert(observe(&a,UINT64_MAX,23)==XW_PLAYER_CLOSED);
 assert(revokes&&submits==6);return 0;
}
