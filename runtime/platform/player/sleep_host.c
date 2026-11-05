#include "sleep_host.h"
#include "host_managed_service.h"
#include "wireless_host.h"
extern unsigned long pthread_self(void);
static int valid(void *context,uint64_t epoch){
 struct xw_sleep_host *host=context;
 if(xw_player_host_original_exiting())return XW_PLAYER_CLOSED;
 return host->native_valid(host->native_context,epoch);
}
static int quiesce(void *context){(void)context;return xw_player_host_service_quiesce();}
static int radio(void *context,uint64_t epoch){
 (void)context;
 int rc=xw_player_host_wireless_prepare_handoff(epoch);
 if(rc==XW_MODE_PENDING)return XW_PLAYER_ACCEPTED;
 return rc?XW_PLAYER_UNCERTAIN:0;
}
static int sdk(void *context){(void)context;return xw_player_host_service_stop();}
static int ack(void *context){
 struct xw_sleep_host *host=context;return host->native_ack(host->native_context);
}
static const struct xw_sleep_retirement_ops operations={valid,quiesce,radio,sdk,ack};
int xw_player_sleep_host_begin(struct xw_sleep_host *host,void *context,
 int (*native_valid)(void *,uint64_t),int (*native_ack)(void *),uint64_t epoch,unsigned long owner){
 if(!host||!native_valid||!native_ack||!epoch||!owner)return XW_PLAYER_INVALID;
 if(pthread_self()!=owner||host->retirement.phase!=XW_SLEEP_IDLE||host->retirement.busy)return XW_PLAYER_BUSY;
 host->native_context=context;host->native_valid=native_valid;host->native_ack=native_ack;
 return xw_sleep_retirement_begin(&host->retirement,&operations,host,epoch,owner);
}
int xw_player_sleep_host_poll(struct xw_sleep_host *host){
 return host?xw_sleep_retirement_poll(&host->retirement):XW_PLAYER_INVALID;
}
int xw_player_sleep_host_resume(struct xw_sleep_host *host,int (*recovery_valid)(void *,uint64_t)){
 if(!host||!recovery_valid)return XW_PLAYER_INVALID;
 struct xw_sleep_retirement *gate=&host->retirement;
 if(gate->busy||pthread_self()!=gate->owner)return XW_PLAYER_BUSY;
 if(gate->phase!=XW_SLEEP_ACKNOWLEDGED)return XW_PLAYER_CLOSED;
 if(xw_player_host_original_exiting())return XW_PLAYER_CLOSED;
 gate->busy=1;
 int rc=recovery_valid(host->native_context,gate->epoch);
 if(!rc){
  rc=xw_player_host_wireless_resume_handoff(gate->epoch);
  if(rc==XW_MODE_PENDING)rc=XW_PLAYER_ACCEPTED;
  else if(rc)rc=XW_PLAYER_UNCERTAIN;
 }
 gate->busy=0;
 if(rc)return rc;
 struct xw_sleep_host empty={0};*host=empty;return 0;
}
