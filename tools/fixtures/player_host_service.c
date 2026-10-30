/* Startup failures are modeled; the production dispatch state machine executes. */
#include "../../runtime/platform/player/player_broker.h"
#include "../../runtime/platform/player/rpc_posix.h"
#include "../../runtime/platform/player/host_hook.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static unsigned long long now=100;
static unsigned clock_fail=1,binds,opens,broker_ticks,server_ticks;
int hb_monotonic_millis(unsigned long long *out){if(clock_fail)return -1;*out=now;return 0;}
int xw_player_broker_bind(struct xw_player_broker *broker,struct xw_player *backend){
 assert(backend&&backend->initialized&&!broker->player.initialized);binds++;
 if(binds==1)return XW_PLAYER_UNAVAILABLE;
 broker->backend=backend;broker->player.initialized=1;return 0;
}
int xw_player_rpc_server_open(struct xw_player_rpc_server *server,struct xw_player *player,const char *endpoint){
 assert(player&&player->initialized&&!strcmp(endpoint,XW_PLAYER_RPC_ENDPOINT));opens++;
 if(opens==1)return XW_PLAYER_BUSY;server->bound=1;return 0;
}
void xw_player_broker_tick(struct xw_player_broker *b,unsigned long long t){assert(b->player.initialized&&t==now);broker_ticks++;}
int xw_player_rpc_server_tick(struct xw_player_rpc_server *s,unsigned long long t){assert(s->bound&&t==now);server_ticks++;return XW_PLAYER_IO;}
int xw_player_host_queue_attach(struct xw_player_broker *b){assert(b->player.initialized);return XW_PLAYER_UNAVAILABLE;}
int main(int argc,char **argv){
 static struct xw_player original;original.initialized=1;
 xw_player_host_dispatch(&original);assert(!binds&&!opens&&!server_ticks);
 clock_fail=0;xw_player_host_dispatch(&original);assert(binds==1&&!opens);
 now=200;xw_player_host_dispatch(&original);assert(binds==1&&!opens);
 if(argc>1){
  assert(!strcmp(argv[1],"--rollback"));now=1;xw_player_host_dispatch(&original);assert(binds==2&&opens==1&&!server_ticks);
  now=2;xw_player_host_dispatch(&original);assert(opens==1);
  now=0;xw_player_host_dispatch(&original);assert(binds==2&&opens==2&&server_ticks==1);
  puts("Owner service: pre-ready clock rollback resets retry deadline without rebinding the retained broker");return 0;
 }
 now=1100;xw_player_host_dispatch(&original);assert(binds==2&&opens==1&&!server_ticks);
 now=1600;xw_player_host_dispatch(&original);assert(binds==2&&opens==1);
 now=2100;xw_player_host_dispatch(&original);assert(binds==2&&opens==2&&server_ticks==1);
 for(unsigned i=0;i<200;i++){now++;xw_player_host_dispatch(&original);}
 assert(binds==2&&opens==2&&server_ticks==201&&broker_ticks==201);
 clock_fail=1;xw_player_host_dispatch(&original);assert(server_ticks==201);
 clock_fail=0;now=1;xw_player_host_dispatch(&original);assert(binds==2&&opens==2&&server_ticks==202&&original.initialized);
 puts("Owner service: clock refusal, rate-limited broker/listener startup recovery, retained broker and bounded dispatch passed");return 0;
}
