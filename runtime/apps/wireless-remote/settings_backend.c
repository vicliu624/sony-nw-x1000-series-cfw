#include "settings_backend.h"
#include "../../platform/player/host_managed_service.h"
#include "../../platform/player/managed_host.h"
#include <unistd.h>
#include <string.h>
extern unsigned long pthread_self(void);
static int original_owner(struct wr_settings_backend *b){return b&&b->phase&&b->owner==pthread_self();}
static int poll_process(struct wr_settings_backend *b){
 int rc=wr_supervisor_process_poll(&b->process);
 if(b->process.reaped&&b->last_start.serial){
  b->last_start.child_reaped=1;
  b->last_start.child_wait_status=b->process.status;
  if(b->last_start.stage==WR_START_OFFERED&&!b->process.stop_sent){
   b->last_start.stage=WR_START_CHILD_EXIT;
   b->last_start.result=rc?rc:XW_PLAYER_UNAVAILABLE;
  }
 }
 return rc;
}
static int retired(struct wr_settings_backend *b){
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(b->process.state==WR_PROCESS_CLOSED)return 0;
 int rc=poll_process(b);
 if(rc)return rc;
 return wr_supervisor_process_close(&b->process);
}
static int stop_retired(void *context,uint64_t generation){
 struct wr_settings_backend *b=context;
 if(!original_owner(b)||generation!=b->generation)return XW_PLAYER_STALE;
 return retired(b);
}
static int native_retired(void *context,uint64_t epoch){
 struct wr_settings_backend *b=context;
 if(!epoch||!original_owner(b))return XW_PLAYER_INVALID;
 /* The host separately validates its native epoch/context before/after this
  * callback. Our process/generation stays fixed through this retirement. */
 return retired(b);
}
static int start_result(struct wr_settings_backend *b,enum wr_settings_start_stage stage,int result){
 b->last_start.stage=stage;b->last_start.result=result;return result;
}
static void poll_backend(void *context){
 struct wr_settings_backend *b=context;if(!original_owner(b)||b->phase==WR_SETTINGS_OFF||b->phase==WR_SETTINGS_RETIRED)return;
 if(b->phase==WR_SETTINGS_FAULT){if(b->process.state&&!b->process.reaped)(void)poll_process(b);return;}
 if(b->phase==WR_SETTINGS_STARTING&&b->wireless_mode(b->context)!=XW_WIRELESS_MODE_ESPNOW)b->phase=WR_SETTINGS_STOPPING;
 if(b->phase==WR_SETTINGS_STOPPING&&!b->process.stop_sent&&!b->process.reaped){
  int stop=wr_supervisor_process_request_stop(&b->process);if(stop&&stop!=XW_PLAYER_BUSY){b->phase=WR_SETTINGS_FAULT;b->error=stop;return;}
 }
 int rc=retired(b);
 if(rc==XW_PLAYER_BUSY)return;
 if(rc){b->phase=WR_SETTINGS_FAULT;b->error=rc;return;}
 int done=xw_player_host_generation_retired(b->generation);
 if(done<0){b->phase=WR_SETTINGS_FAULT;b->error=done;return;}
 if(!done&&xw_player_host_service_phase()==XW_HOST_ACTIVE){rc=xw_player_host_service_stop_generation(b->generation);if(rc!=XW_PLAYER_BUSY&&rc){b->phase=WR_SETTINGS_FAULT;b->error=rc;return;}}
 done=xw_player_host_generation_retired(b->generation);
 if(done<0){b->phase=WR_SETTINGS_FAULT;b->error=done;return;}
 b->phase=done?WR_SETTINGS_RETIRED:WR_SETTINGS_STOPPING;
}
static int request(void *context,uint64_t serial){
 struct wr_settings_backend *b=context;
 if(!original_owner(b)||!serial||serial<=b->last_request)return XW_PLAYER_STALE;
 b->last_request=serial;
 unsigned explicit_target=b->pending_enabled;b->pending_enabled=0;
 if(explicit_target==1)return wr_settings_backend_request_stop(b);
 if(explicit_target==2&&b->phase==WR_SETTINGS_STARTING)return 0;
 if(b->phase==WR_SETTINGS_STOPPING)return XW_PLAYER_BUSY;
 if(b->phase==WR_SETTINGS_RETIRED)return XW_PLAYER_STALE;
 if(b->phase==WR_SETTINGS_FAULT)return XW_PLAYER_UNAVAILABLE;
 if(b->phase==WR_SETTINGS_STARTING){
  return wr_settings_backend_request_stop(b);
 }
 b->last_start=(struct wr_settings_start_result){.serial=serial};
 unsigned host_phase=xw_player_host_service_phase();
 if(host_phase&&host_phase!=XW_HOST_STOPPED)return start_result(b,WR_START_HOST,XW_PLAYER_BUSY);
 if(b->wireless_mode(b->context)!=XW_WIRELESS_MODE_ESPNOW)return start_result(b,WR_START_MODE,XW_PLAYER_UNAVAILABLE);
 if(b->prepare){
  uint64_t generation=b->generation;int prepared=b->prepare(b->context,&generation);
  if(prepared)return start_result(b,WR_START_PREPARE,prepared);
  if(!generation||generation<b->generation)return start_result(b,WR_START_PREPARE,XW_PLAYER_STALE);
  b->generation=generation;
 }
 int rc=wr_supervisor_process_start(&b->process,b->generation,b->context,b->admit);
 if(rc)return start_result(b,WR_START_PROCESS,rc);
 b->phase=WR_SETTINGS_STARTING;
 const uint32_t grants=XW_PLAYER_GRANT_READ|XW_PLAYER_GRANT_CONTROL|XW_PLAYER_GRANT_BROWSE;
 rc=xw_player_host_session_offer(b->process.delivery,grants,grants,b->generation);
 int closed=wr_supervisor_process_delivery_close(&b->process);
 if(rc||closed){b->phase=WR_SETTINGS_FAULT;b->error=rc?rc:closed;return start_result(b,WR_START_OFFER,b->error);}
 rc=xw_player_host_stop_dependency(b,stop_retired);
 if(!rc)rc=xw_player_host_exit_dependency(b,native_retired);
 if(rc){b->phase=WR_SETTINGS_FAULT;b->error=rc;return start_result(b,WR_START_DEPENDENCIES,rc);}
 return start_result(b,WR_START_OFFERED,XW_PLAYER_ACCEPTED);
}
int wr_settings_backend_start_result(struct wr_settings_backend *b,struct wr_settings_start_result *out){
 if(!out)return XW_PLAYER_INVALID;
 if(!original_owner(b))return XW_PLAYER_BUSY;
 *out=b->last_start;return 0;
}
int wr_settings_backend_query(struct wr_settings_backend *b,struct wr_settings_view *out){
 if(!out)return XW_PLAYER_INVALID;
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(xw_player_host_original_exiting())return XW_PLAYER_CLOSED;
 struct wr_settings_view view={b->phase,b->pending_enabled!=0,
  b->phase==WR_SETTINGS_FAULT?-1:b->pending_enabled?b->pending_enabled==2:b->phase==WR_SETTINGS_STARTING,b->error};
 *out=view;return 0;
}
int wr_settings_backend_request_enabled(struct wr_settings_backend *b,int enabled){
 if(enabled!=0&&enabled!=1)return XW_PLAYER_INVALID;
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(xw_player_host_original_exiting())return XW_PLAYER_CLOSED;
 unsigned target=enabled?2u:1u;
 if(b->pending_enabled)return b->pending_enabled==target?XW_PLAYER_ACCEPTED:XW_PLAYER_BUSY;
 if(b->phase==WR_SETTINGS_FAULT)return XW_PLAYER_UNAVAILABLE;
 if((enabled&&b->phase==WR_SETTINGS_STARTING)||
    (!enabled&&(b->phase==WR_SETTINGS_OFF||b->phase==WR_SETTINGS_RETIRED)))return 0;
 if(b->phase==WR_SETTINGS_STOPPING)return XW_PLAYER_BUSY;
 if(b->phase==WR_SETTINGS_RETIRED)return XW_PLAYER_STALE;
 b->pending_enabled=target;
 int rc=xw_player_host_settings_enqueue();
 if(rc!=XW_PLAYER_ACCEPTED)b->pending_enabled=0;
 return rc;
}
int wr_settings_backend_bind(struct wr_settings_backend *b,uint64_t generation,void *context,int (*admit)(void *),int (*wireless_mode)(void *)){
 if(!b||b->phase||!generation||!admit||!wireless_mode)return XW_PLAYER_INVALID;
 b->context=context;b->admit=admit;b->wireless_mode=wireless_mode;b->generation=generation;b->owner=pthread_self();
 int rc=xw_player_host_settings_bind_backend(b,request,poll_backend);
 if(rc)return rc;
 b->phase=WR_SETTINGS_OFF;return 0;
}
int wr_settings_backend_unbind(struct wr_settings_backend *b){
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(b->phase!=WR_SETTINGS_OFF&&b->phase!=WR_SETTINGS_RETIRED)return XW_PLAYER_BUSY;
 int rc=xw_player_host_settings_unbind();if(!rc){b->phase=0;b->prepare=0;}return rc;
}
int wr_settings_backend_renew(struct wr_settings_backend *b,uint64_t generation){
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(!generation||generation<=b->generation)return XW_PLAYER_STALE;
 if(b->phase!=WR_SETTINGS_RETIRED)return XW_PLAYER_BUSY;
 struct wr_supervisor_process *p=&b->process;
 if(p->owner!=(int)getpid())return XW_PLAYER_UNAVAILABLE;
 if(p->state!=WR_PROCESS_CLOSED||!p->reaped||(p->status&&!p->startup_refused)||p->delivery>=0||p->log_reader>=0||p->stop_fd>=0)return XW_PLAYER_UNAVAILABLE;
 if(xw_player_host_service_phase()!=XW_HOST_STOPPED)return XW_PLAYER_BUSY;
 int rc=xw_player_host_service_stop();if(rc)return rc;
 memset(p,0,sizeof *p);b->generation=generation;b->error=0;b->phase=WR_SETTINGS_OFF;return 0;
}
int wr_settings_backend_prepare(struct wr_settings_backend *b,int (*prepare)(void *,uint64_t *)){
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(!prepare)return XW_PLAYER_INVALID;
 if(b->phase!=WR_SETTINGS_OFF||b->process.state||b->prepare)return XW_PLAYER_BUSY;
 b->prepare=prepare;return 0;
}
int wr_settings_backend_cleanup_tick(struct wr_settings_backend *b){
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(!xw_player_host_original_exiting())return XW_PLAYER_INVALID;
 poll_backend(b);return b->phase==WR_SETTINGS_FAULT?XW_PLAYER_UNCERTAIN:0;
}
int wr_settings_backend_request_stop(struct wr_settings_backend *b){
 if(!original_owner(b))return XW_PLAYER_BUSY;
 if(b->phase==WR_SETTINGS_OFF||b->phase==WR_SETTINGS_RETIRED)return 0;
 if(b->phase==WR_SETTINGS_STOPPING)return XW_PLAYER_BUSY;
 if(b->phase!=WR_SETTINGS_STARTING)return XW_PLAYER_UNAVAILABLE;
 int rc=wr_supervisor_process_request_stop(&b->process);
 if(!rc||rc==XW_PLAYER_BUSY){b->phase=WR_SETTINGS_STOPPING;return XW_PLAYER_ACCEPTED;}
 b->phase=WR_SETTINGS_FAULT;b->error=rc;return rc;
}
