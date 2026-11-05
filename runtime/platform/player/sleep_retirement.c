#include "sleep_retirement.h"
extern unsigned long pthread_self(void);
static int failed(struct xw_sleep_retirement *gate,int result){
 gate->failure=result;gate->phase=XW_SLEEP_FAILED;gate->busy=0;return result;
}
int xw_sleep_retirement_begin(struct xw_sleep_retirement *gate,
 const struct xw_sleep_retirement_ops *ops,void *context,uint64_t epoch,unsigned long owner){
 if(!gate||!ops||!ops->valid||!ops->quiesce||!ops->retire_radio||
    !ops->stop_sdk||!ops->original_ack||!epoch||!owner)return XW_PLAYER_INVALID;
 if(pthread_self()!=owner||gate->busy||gate->phase!=XW_SLEEP_IDLE)return XW_PLAYER_BUSY;
 gate->ops=ops;gate->context=context;gate->epoch=epoch;gate->owner=owner;gate->busy=1;
 int rc=ops->valid(context,epoch);
 if(rc)return failed(gate,rc);
 gate->phase=XW_SLEEP_DRAINING;
 rc=ops->quiesce(context);
 if(rc)return failed(gate,rc);
 gate->busy=0;return XW_PLAYER_ACCEPTED;
}
int xw_sleep_retirement_poll(struct xw_sleep_retirement *gate){
 if(!gate||!gate->ops)return XW_PLAYER_INVALID;
 if(gate->busy||pthread_self()!=gate->owner)return XW_PLAYER_BUSY;
 if(gate->phase==XW_SLEEP_FAILED)return gate->failure;
 if(gate->phase==XW_SLEEP_ACKNOWLEDGED)return XW_PLAYER_OK;
 if(gate->phase!=XW_SLEEP_DRAINING)return XW_PLAYER_CLOSED;
 gate->busy=1;
 int rc=gate->ops->valid(gate->context,gate->epoch);
 if(rc)return failed(gate,rc);
 rc=gate->ops->retire_radio(gate->context,gate->epoch);
 if(rc==XW_PLAYER_ACCEPTED){gate->busy=0;return XW_PLAYER_ACCEPTED;}
 if(rc)return failed(gate,rc);
 rc=gate->ops->stop_sdk(gate->context);
 if(rc==XW_PLAYER_BUSY){gate->busy=0;return XW_PLAYER_ACCEPTED;}
 if(rc)return failed(gate,rc);
 rc=gate->ops->valid(gate->context,gate->epoch);
 if(rc)return failed(gate,rc);
 /* Mark in progress before the native call so reentrancy cannot send twice. */
 rc=gate->ops->original_ack(gate->context);
 if(rc)return failed(gate,rc);
 gate->phase=XW_SLEEP_ACKNOWLEDGED;gate->busy=0;return XW_PLAYER_OK;
}
