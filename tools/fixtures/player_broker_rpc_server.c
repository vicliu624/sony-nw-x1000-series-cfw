/* Actual broker/IPC workers; original player and database boundaries modeled. */
#define main broker_unit_main
#define hb_monotonic_millis broker_unit_clock
#include "player_broker.c"
#undef hb_monotonic_millis
#undef main
#include "../../runtime/platform/player/rpc_posix.h"
#include <signal.h>
extern int hb_monotonic_millis(unsigned long long *);
static volatile sig_atomic_t quitting;
static enum xw_play_state model_state=XW_PLAY_PLAYING;
static int model_volume=12;
#ifdef XW_TEST_SOURCE
#include "../../runtime/platform/player/source_service.h"
static struct xw_source_service source_service;
static struct xw_stock_gui source_gui;
static unsigned source_submissions,pending_track;
static unsigned long long apply_after;
int xw_stock_media_validate_audio(struct xw_stock_media *s,const struct xw_media_id *id,struct xw_stock_audio_identity *out){
 assert(pthread_self()!=s->gui_owner);s->worker_set=1;s->worker=pthread_self();poll(0,0,20);
 memset(out,0,sizeof *out);out->id=*id;out->media_type=1;return 0;
}
int xw_stock_gui_read(struct xw_stock_gui *g,struct xw_stock_gui_view *out){
 assert(g==&source_gui&&g->owner==pthread_self());memset(out,0,sizeof *out);out->active=available;
 out->mode=model_state==XW_PLAY_PAUSED?2:1;out->state=out->mode==2?2:5;return 0;
}
int xw_stock_source_submit(struct xw_stock_gui *g,const struct xw_media_id *id,struct xw_stock_source_result *out){
 assert(g==&source_gui&&g->owner==pthread_self());uint32_t domain,number;assert(!xw_local_media_id_parse(id,&domain,&number));
 unsigned long long clock;assert(!hb_monotonic_millis(&clock));pending_track=number;apply_after=clock+50;
 source_submissions++;out->attempted=out->moved=1;out->ticket=100+source_submissions;return XW_PLAYER_ACCEPTED;
}
#endif
static void stop_server(int sig){(void)sig;quitting=1;}
static int observed(void *ctx,struct xw_player_snapshot *out){int rc=snapshot(ctx,out);out->state=model_state;out->volume=model_volume;return rc;}
#ifdef XW_TEST_NATIVE_QUEUE
#include "player_native_queue_model.h"
#endif
static int control(void *ctx,const struct xw_player_command *c){
 if(c->operation==XW_OP_NEXT){int rc=command(ctx,c);
#ifdef XW_TEST_NATIVE_QUEUE
 atomic_store(&model_session,8);
#endif
 return rc;}

 if(c->operation==XW_OP_PREVIOUS){if(track>1)track--;
#ifdef XW_TEST_NATIVE_QUEUE
 atomic_store(&model_session,7);
#endif
 return XW_PLAYER_ACCEPTED;}
 if(c->operation==XW_OP_PLAY){model_state=XW_PLAY_PLAYING;return XW_PLAYER_ACCEPTED;}
 if(c->operation==XW_OP_PAUSE){model_state=XW_PLAY_PAUSED;return XW_PLAYER_ACCEPTED;}
 if(c->operation==XW_OP_STEP_VOLUME){if(c->value!=1&&c->value!=-1)return XW_PLAYER_INVALID;model_volume+=c->value;if(model_volume<0)model_volume=0;if(model_volume>30)model_volume=30;return XW_PLAYER_ACCEPTED;}
 return XW_PLAYER_UNSUPPORTED;
}
int main(int argc,char **argv){
 assert(argc==2);assert(!pthread_mutex_init((void *)&counters,0));struct xw_player_provider provider={XW_PLAYER_API,(1u<<XW_OP_PLAY)|(1u<<XW_OP_PAUSE)|(1u<<XW_OP_NEXT)|(1u<<XW_OP_PREVIOUS)|(1u<<XW_OP_STEP_VOLUME),0,observed,control,0,close_backend};
 static struct xw_player_rpc_server endpoint;
 assert(!xw_player_bind(&original,&provider)&&!xw_player_broker_bind(&broker,&original));assert(!xw_player_rpc_server_open(&endpoint,&broker.player,argv[1]));
#ifdef XW_TEST_SOURCE
 struct xw_player_source_provider source;source_gui.owner=pthread_self();source_gui.bound=1;
 assert(!xw_source_service_init(&source_service,&source_gui,&source)&&!xw_player_broker_attach_source(&broker,&source));
#endif
#ifdef XW_TEST_NATIVE_QUEUE
 start_queue_model();
#endif
 signal(SIGTERM,stop_server);puts("READY");fflush(stdout);
 while(!quitting){unsigned long long time;assert(!hb_monotonic_millis(&time));
#ifdef XW_TEST_SOURCE
 if(apply_after&&time>=apply_after){track=pending_track;model_state=XW_PLAY_PLAYING;apply_after=0;}
#endif
 xw_player_broker_tick(&broker,time);int rc=xw_player_rpc_server_tick(&endpoint,time);assert(rc==0||rc==XW_PLAYER_ACCEPTED||rc==XW_PLAYER_IO);poll(0,0,1);}
 assert(!xw_player_rpc_server_close(&endpoint));int rc=XW_PLAYER_BUSY;
#ifdef XW_TEST_SOURCE
 assert(source_submissions==1);
#endif
 for(unsigned i=0;i<2000&&rc==XW_PLAYER_BUSY;i++){rc=xw_player_close(&broker.player);if(rc==XW_PLAYER_BUSY)poll(0,0,1);}assert(!rc&&original.initialized&&!backend_closed);
#ifdef XW_TEST_NATIVE_QUEUE
 stop_queue_model();
#endif
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);pthread_mutex_unlock((void *)&counters);assert(!xw_player_close(&original));assert(!pthread_mutex_destroy((void *)&counters));puts("CLEAN: endpoint closed, workers drained, original backend preserved then explicitly closed");return 0;
}
