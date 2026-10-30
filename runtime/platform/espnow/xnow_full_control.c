#include "xnow_full_control.h"
#include <string.h>
#include <unistd.h>
static int owner(const struct xnow_full_control *c){return c&&c->initialized&&c->manager.owner==(int)getpid();}
static int lease(void *context){struct xnow_full_control *c=context;return owner(c)&&!c->uncertain&&c->manager.held&&c->session.lease&&c->options.lease_valid(c->options.context);}
int xnow_full_control_init(struct xnow_full_control *c,const struct xnow_full_control_options *o){
 if(!c)return XNOW_ARGUMENT;
 memset(c,0,sizeof(*c));c->radio.fd=-1;
 if(!o||!o->profile||!o->profile->ranges||!o->profile->count||o->profile->count>16||!o->radio_guard||!o->ipc_guard||!o->lease_valid||!o->random||o->channel<1||o->channel>13||o->encrypted_limit>17)return XNOW_ARGUMENT;
 c->options=*o;xnow_session_init(&c->session,o->allow_disconnect);xnow_manager_init(&c->manager);xnow_loader_job_init(&c->job);c->initialized=1;return 0;
}
static int complete(struct xnow_full_control *c,enum xnow_session_action a,int result){
 if(xnow_session_complete(&c->session,a,result)){c->uncertain=1;return XNOW_UNCERTAIN;}
 if(c->manager.uncertain)c->uncertain=1;
 if(c->session.phase>=XNOW_SESSION_STOPPING&&!c->endpoint_ready)xnow_sd8686_full_close(&c->radio);
 return c->uncertain?XNOW_UNCERTAIN:(int)c->session.phase;
}
int xnow_full_control_step(struct xnow_full_control *c){
 if(!owner(c)||c->stepping)return XNOW_ARGUMENT;
 if(c->uncertain)return XNOW_UNCERTAIN;
 if(c->job.pid){int result;c->stepping=1;int polled=xnow_loader_job_poll(&c->job,&result);c->stepping=0;if(polled<0){c->uncertain=1;return XNOW_UNCERTAIN;}if(polled==1)return c->session.phase;return complete(c,c->job.action,result);}
 if(c->endpoint_ready){
  if(!lease(c)){c->uncertain=1;return XNOW_UNCERTAIN;}
  if(c->stop_requested){int r=xnow_endpoint_stop_step(&c->endpoint);if(r==XNOW_PENDING)return c->session.phase;if(r){c->uncertain=1;return XNOW_UNCERTAIN;}c->endpoint_ready=0;xnow_session_stop(&c->session);xnow_sd8686_full_close(&c->radio);}
 }
 if(c->session.phase!=XNOW_SESSION_STARTING&&c->session.phase!=XNOW_SESSION_STOPPING)return c->session.phase;
 enum xnow_session_action action=xnow_session_take(&c->session);if(action==XNOW_SESSION_NONE)return c->session.phase;
 c->stepping=1;int result;
 switch(action){
 case XNOW_SESSION_PREFLIGHT:result=c->options.radio_guard(c->options.context,action);break;
 case XNOW_SESSION_ACQUIRE:case XNOW_SESSION_INSPECT:case XNOW_SESSION_DISCONNECT:case XNOW_SESSION_RECONNECT:case XNOW_SESSION_RELEASE:
  result=xnow_manager_execute(&c->manager,&c->session,c->options.context,c->options.ipc_guard);break;
 case XNOW_SESSION_UNLOAD:case XNOW_SESSION_RESTORE_UNLOAD:case XNOW_SESSION_LOAD_CANDIDATE:case XNOW_SESSION_LOAD_STOCK:case XNOW_SESSION_WAKE:case XNOW_SESSION_RESTORE_WAKE:case XNOW_SESSION_INITIALIZE:case XNOW_SESSION_RESTORE_INITIALIZE:
  if(action==XNOW_SESSION_UNLOAD||action==XNOW_SESSION_RESTORE_UNLOAD||action==XNOW_SESSION_LOAD_CANDIDATE||action==XNOW_SESSION_LOAD_STOCK)xnow_sd8686_full_close(&c->radio);
  result=xnow_loader_job_start(&c->job,&c->session,c->options.context,c->options.radio_guard);c->stepping=0;if(!result)return c->session.phase;return complete(c,action,result);
 case XNOW_SESSION_VERIFY_CANDIDATE:
  result=c->options.radio_guard(c->options.context,action);if(!result)result=xnow_sd8686_full_probe(&c->radio,c->options.profile,c,lease,&c->bounded,c->local_mac);break;
 case XNOW_SESSION_CONFIGURE:
  result=c->options.radio_guard(c->options.context,action);
  if(!result)result=xnow_sd8686_full_channel_set(&c->radio,&c->session,c->options.channel);
  if(!result)result=xnow_full_open(&c->backend,&c->bounded,&c->options.profile->layout);
  if(!result)result=xnow_endpoint_init(&c->endpoint,&c->backend,c->options.channel,c->options.encrypted_limit,c->options.context,c->options.random);
  if(!result)c->endpoint_ready=1;
  break;
 case XNOW_SESSION_VERIFY_STOCK:result=c->options.radio_guard(c->options.context,action);if(!result)result=xnow_sd8686_stock_verify();break;
 default:result=XNOW_ARGUMENT;break;
 }
 c->stepping=0;return complete(c,action,result);
}
void xnow_full_control_stop(struct xnow_full_control *c){
 if(!owner(c))return;
 c->stop_requested=1;
 if(c->endpoint_ready)c->endpoint.stopping=1;
 if(!c->endpoint_ready)xnow_session_stop(&c->session);
}
int xnow_full_control_retry_restore(struct xnow_full_control *c){if(!owner(c)||c->uncertain||c->stepping||c->job.pid||c->manager.uncertain||c->endpoint_ready)return XNOW_UNCERTAIN;return xnow_session_retry_restore(&c->session);}
struct xnow_endpoint *xnow_full_control_endpoint(struct xnow_full_control *c){return owner(c)&&!c->stop_requested&&c->endpoint_ready&&c->session.phase==XNOW_SESSION_READY&&lease(c)?&c->endpoint:0;}
int xnow_full_control_finished(const struct xnow_full_control *c){return owner(c)&&!c->uncertain&&!c->job.pid&&!c->manager.held&&!c->endpoint_ready&&c->session.phase==XNOW_SESSION_DONE;}
