#include "radio_release.h"
#include "../espnow/xnow_power_off.h"
#include <unistd.h>
int xw_wireless_radio_release_step(struct xnow_full_control *c,void *context,int (*exclusive)(void *)){
 if(!c||!exclusive||!c->initialized||c->manager.owner!=(int)getpid()||c->stepping)return XNOW_ARGUMENT;
 if(c->uncertain||c->manager.uncertain)return XNOW_UNCERTAIN;
 /* One consumer cannot destroy another application's saved connection. */
 if(c->options.allow_disconnect||c->session.was_connected)return XNOW_RADIO_REJECTED;
 if(!c->stop_requested)return XNOW_RADIO_REJECTED;
 if(c->session.phase!=XNOW_SESSION_STOPPING||c->job.pid||c->endpoint_ready||
    c->session.pending||c->session.next!=XNOW_SESSION_RELEASE)
  return xnow_full_control_step(c);
 c->stepping=1;
 if(c->options.radio_guard(c->options.context,XNOW_SESSION_RELEASE)){
  c->uncertain=1;c->stepping=0;return XNOW_UNCERTAIN;
 }
 enum xnow_session_action action=xnow_session_take(&c->session);
 if(action!=XNOW_SESSION_RELEASE){c->uncertain=1;c->stepping=0;return XNOW_UNCERTAIN;}
 int rc=xnow_manager_power_off(&c->manager,&c->session,context,exclusive);
 if(rc){c->uncertain=1;c->stepping=0;return XNOW_UNCERTAIN;}
 rc=xnow_manager_execute(&c->manager,&c->session,c->options.context,c->options.ipc_guard);
 if(xnow_session_complete(&c->session,action,rc)||c->manager.uncertain)c->uncertain=1;
 c->stepping=0;
 return c->uncertain?XNOW_UNCERTAIN:(int)c->session.phase;
}
