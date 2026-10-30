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
 assert(argc==2);struct xw_player_provider provider={XW_PLAYER_API,(1u<<XW_OP_PLAY)|(1u<<XW_OP_PAUSE)|(1u<<XW_OP_NEXT)|(1u<<XW_OP_PREVIOUS)|(1u<<XW_OP_STEP_VOLUME),0,observed,control,0,close_backend};
 static struct xw_player_rpc_server endpoint;
 assert(!xw_player_bind(&original,&provider)&&!xw_player_broker_bind(&broker,&original));assert(!xw_player_rpc_server_open(&endpoint,&broker.player,argv[1]));
#ifdef XW_TEST_NATIVE_QUEUE
 start_queue_model();
#endif
 signal(SIGTERM,stop_server);puts("READY");fflush(stdout);
 while(!quitting){unsigned long long time;assert(!hb_monotonic_millis(&time));xw_player_broker_tick(&broker,time);int rc=xw_player_rpc_server_tick(&endpoint,time);assert(rc==0||rc==XW_PLAYER_ACCEPTED||rc==XW_PLAYER_IO);poll(0,0,1);}
 assert(!xw_player_rpc_server_close(&endpoint));int rc=XW_PLAYER_BUSY;
 for(unsigned i=0;i<2000&&rc==XW_PLAYER_BUSY;i++){rc=xw_player_close(&broker.player);if(rc==XW_PLAYER_BUSY)poll(0,0,1);}assert(!rc&&original.initialized&&!backend_closed);
#ifdef XW_TEST_NATIVE_QUEUE
 stop_queue_model();
#endif
 pthread_mutex_lock(&counters);assert(opened==closed&&!live);pthread_mutex_unlock(&counters);assert(!xw_player_close(&original));puts("CLEAN: endpoint closed, workers drained, original backend preserved then explicitly closed");return 0;
}
