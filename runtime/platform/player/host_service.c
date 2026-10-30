/* Local owner dispatcher; native reads are scheduled in background workers. */
#include "host_hook.h"
#include "rpc_posix.h"
#include "player_broker.h"
#include "host_queue.h"
#include "../../store/deadline.h"
static struct xw_player_rpc_server service;
static unsigned ready;
static unsigned long long next_attempt,last;
static struct xw_player_broker broker;
void xw_player_host_dispatch(struct xw_player *player)
{
    unsigned long long now;
    if (hb_monotonic_millis(&now)) return;
    if(now<last)next_attempt=0;
    last=now;
    if(!ready&&now>=next_attempt){
        next_attempt=now>~0ull-1000u?~0ull:now+1000u;
        /* Preserve an already-bound broker after a temporary listener failure.
         * No commands are queued or replayed by this startup retry. */
        int rc=broker.player.initialized?0:xw_player_broker_bind(&broker,player);
        if(!rc)ready=xw_player_rpc_server_open(&service,&broker.player,XW_PLAYER_RPC_ENDPOINT)==0;
    }
    /* Adapter requires a matching observed Met list and current GUI session. */
    if(ready&&!broker.queue.browse)xw_player_host_queue_attach(&broker);
    if (ready) {xw_player_broker_tick(&broker,now);xw_player_rpc_server_tick(&service,now);}
}
