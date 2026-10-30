#include "host_queue.h"
#include "host_hook.h"
#include "queue_browser.h"
#include "stock_info.h"
#include <string.h>
extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *,const void *),pthread_mutex_trylock(void *),pthread_mutex_unlock(void *);
static union xw_pthread_storage gate;
/* Initialized by startup preload constructor before application threads exist;
 * never destroyed or reinitialized while this process-lifetime DSO is loaded. */
static unsigned gate_ready,seen,phase;
static int met_error;
static struct xw_stock_info info;
static struct xw_stock_session_key target;
static unsigned target_valid;
static uint32_t owner_list;
static struct xw_queue_browser browser;
static struct xw_stock_queue_owner met_owner;
#define ACTIVE 1u
#define STOPPING 2u
#define STOPPED 3u
#define CLOSED 4u
__attribute__((constructor)) static void queue_gate_init(void){gate_ready=pthread_mutex_init(&gate,0)==0;}
static int queue_browse(void *ctx,const struct xw_media_query *q,uint64_t now,struct xw_media_item *items,struct xw_media_page *page){
 (void)ctx;if(!gate_ready)return XW_PLAYER_UNAVAILABLE;if(pthread_mutex_trylock(&gate))return XW_PLAYER_BUSY;
 int rc=phase!=ACTIVE?XW_PLAYER_CLOSED:0;
 if(!rc){
  struct xw_stock_session_key key;rc=xw_stock_info_session_key(&info,&key);
  if(rc){target_valid=0;xw_queue_browser_revoke(&browser,now);}
  else if(!target_valid||key.list!=target.list||key.number!=target.number){
   rc=xw_queue_browser_revoke(&browser,now);if(!rc){target=key;target_valid=1;met_error=0;}
  }
  if(!rc)rc=met_error?met_error:xw_queue_browser_browse(&browser,q,now,items,page);
 }
 pthread_mutex_unlock(&gate);return rc;
}
static int queue_revoke(void *ctx,uint64_t now){
 (void)ctx;if(!gate_ready)return XW_PLAYER_UNAVAILABLE;if(pthread_mutex_trylock(&gate))return XW_PLAYER_BUSY;
 int rc=phase==ACTIVE?xw_queue_browser_revoke(&browser,now):XW_PLAYER_CLOSED;pthread_mutex_unlock(&gate);return rc;
}
static int queue_close(void *ctx){
 (void)ctx;if(!gate_ready)return XW_PLAYER_UNAVAILABLE;if(pthread_mutex_trylock(&gate))return XW_PLAYER_BUSY;
 int rc=XW_PLAYER_BUSY;
 if(phase==ACTIVE)phase=STOPPING;
 /* Met acknowledges only after releasing/unbinding its native owner state.
  * Future callbacks continue through the gate but cannot touch the browser. */
 if(phase==STOPPED){rc=xw_queue_browser_close(&browser);if(!rc){rc=xw_stock_info_unbind(&info);if(!rc){phase=CLOSED;target_valid=0;}}}
 else if(phase==CLOSED)rc=0;
 pthread_mutex_unlock(&gate);return rc;
}
int xw_player_host_queue_attach(struct xw_player_broker *broker){
 if(!gate_ready)return XW_PLAYER_UNAVAILABLE;if(pthread_mutex_trylock(&gate))return XW_PLAYER_BUSY;
 int rc=XW_PLAYER_UNAVAILABLE;
 if(seen&&!phase){
  rc=xw_stock_info_bind(&info);
  if(!rc)rc=xw_stock_info_session_key(&info,&target);
  if(rc){xw_stock_info_unbind(&info);pthread_mutex_unlock(&gate);return rc;}
  target_valid=1;rc=xw_queue_browser_init(&browser);
  if(!rc){struct xw_player_queue_provider provider={&browser,queue_browse,queue_revoke,queue_close};rc=xw_player_broker_attach_queue(broker,&provider);if(!rc)phase=ACTIVE;else{xw_queue_browser_close(&browser);xw_stock_info_unbind(&info);target_valid=0;}}
  else{xw_stock_info_unbind(&info);target_valid=0;}
 }else if(phase==ACTIVE)rc=0;
 else if(phase)rc=XW_PLAYER_CLOSED;
 pthread_mutex_unlock(&gate);return rc;
}
void xw_player_host_met_dispatch(uint32_t session,uint32_t cancel,uint32_t session_list){
 (void)cancel;if(!gate_ready||pthread_mutex_trylock(&gate))return;
 seen=1;
 if(phase==STOPPING){
  if(met_owner.bound&&met_owner.owner!=pthread_self()){pthread_mutex_unlock(&gate);return;}
  int rc=met_owner.bound?xw_stock_queue_owner_unbind(&met_owner):0;
  if(!rc){phase=STOPPED;owner_list=0;}else met_error=rc;
 }else if(phase==ACTIVE){
  /* Retire a previous service only on its original owner thread. No retained
   * sequence is carried between callbacks; a new service waits for this ack. */
  if(met_owner.bound&&met_owner.owner==pthread_self()&&target_valid&&owner_list!=target.list){
   int rc=xw_stock_queue_owner_unbind(&met_owner);if(rc)met_error=rc;else owner_list=0;
  }
  if(!target_valid||session_list!=target.list||(met_owner.bound&&met_owner.owner!=pthread_self())){pthread_mutex_unlock(&gate);return;}
  unsigned already_bound=met_owner.bound;int rc=already_bound?0:xw_stock_queue_owner_bind(&met_owner);
  if(!rc&&!already_bound)owner_list=session_list;
  if(rc)met_error=rc;
  else if(target_valid){
   rc=xw_stock_queue_owner_session_matches(&met_owner,session,session_list,&target);
   if(!rc){met_error=0;xw_queue_browser_capture(&browser,&met_owner,session);}
   else if(rc!=XW_PLAYER_STALE)met_error=rc;
  }
 }
 pthread_mutex_unlock(&gate);
}
