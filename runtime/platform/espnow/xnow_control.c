#include "xnow_control.h"
#include <string.h>
#include <unistd.h>
static int owner(const struct xnow_control *c){return c&&c->initialized&&c->manager.owner==(int)getpid();}
int xnow_control_init(struct xnow_control *c,const struct xnow_control_options *options){
    if(!c)return XNOW_ARGUMENT;
    memset(c,0,sizeof(*c));c->radio.fd=-1;
    if(!options||!options->radio_guard||!options->ipc_guard||options->channel<1||options->channel>13)return XNOW_ARGUMENT;
    c->options=*options;xnow_session_init(&c->session,options->allow_disconnect);
    xnow_manager_init(&c->manager);xnow_loader_job_init(&c->job);c->initialized=1;return XNOW_OK;
}
int xnow_control_init_stock_rehearsal(struct xnow_control *c,const struct xnow_control_options *options){
    int result=xnow_control_init(c,options);
    if(!result)c->stock_rehearsal=1;
    return result;
}
static int complete(struct xnow_control *c,enum xnow_session_action action,int result){
    if(xnow_session_complete(&c->session,action,result)){c->uncertain=1;return XNOW_UNCERTAIN;}
    /* Inspect(state3) or completed disconnect is the boundary before any
     * candidate action. Reuse restoration without falsely cancelling success. */
    if(c->stock_rehearsal&&c->session.phase==XNOW_SESSION_STARTING&&
       ((action==XNOW_SESSION_INSPECT&&result==3)||
        (action==XNOW_SESSION_DISCONNECT&&result==0))){
        c->session.phase=XNOW_SESSION_STOPPING;
        c->session.next=XNOW_SESSION_RESTORE_UNLOAD;
        c->session.changed=1;
    }
    if(c->manager.uncertain)c->uncertain=1;
    if(c->uncertain||c->session.phase>=XNOW_SESSION_STOPPING)xnow_sd8686_close(&c->radio);
    return c->uncertain?XNOW_UNCERTAIN:(int)c->session.phase;
}
int xnow_control_step(struct xnow_control *c){
    enum xnow_session_action action;int result;
    if(!owner(c)||c->stepping)return XNOW_ARGUMENT;
    if(c->uncertain)return XNOW_UNCERTAIN;
    if(c->job.pid){
        int child_result,polled;
        c->stepping=1;polled=xnow_loader_job_poll(&c->job,&child_result);
        c->stepping=0;
        if(polled<0){c->uncertain=1;xnow_sd8686_close(&c->radio);return XNOW_UNCERTAIN;}
        if(polled==1)return c->session.phase;
        return complete(c,c->job.action,child_result);
    }
    if(c->session.phase!=XNOW_SESSION_STARTING&&c->session.phase!=XNOW_SESSION_STOPPING)return c->session.phase;
    action=xnow_session_take(&c->session);if(action==XNOW_SESSION_NONE)return c->session.phase;
    c->stepping=1;
    switch(action){
    case XNOW_SESSION_PREFLIGHT:result=c->options.radio_guard(c->options.context,action);break;
    case XNOW_SESSION_ACQUIRE:case XNOW_SESSION_INSPECT:case XNOW_SESSION_DISCONNECT:
    case XNOW_SESSION_RECONNECT:case XNOW_SESSION_RELEASE:
        result=xnow_manager_execute(&c->manager,&c->session,c->options.context,c->options.ipc_guard);break;
    case XNOW_SESSION_UNLOAD:case XNOW_SESSION_RESTORE_UNLOAD:
    case XNOW_SESSION_LOAD_CANDIDATE:case XNOW_SESSION_LOAD_STOCK:
    case XNOW_SESSION_WAKE:case XNOW_SESSION_RESTORE_WAKE:
    case XNOW_SESSION_INITIALIZE:case XNOW_SESSION_RESTORE_INITIALIZE:
        if(action==XNOW_SESSION_UNLOAD||action==XNOW_SESSION_RESTORE_UNLOAD||
           action==XNOW_SESSION_LOAD_CANDIDATE||action==XNOW_SESSION_LOAD_STOCK)xnow_sd8686_close(&c->radio);
        result=xnow_loader_job_start(&c->job,&c->session,c->options.context,c->options.radio_guard);
        c->stepping=0;if(!result)return c->session.phase;
        return complete(c,action,result);
    case XNOW_SESSION_VERIFY_CANDIDATE:
        result=c->options.radio_guard(c->options.context,action);
        if(!result)result=xnow_sd8686_open(&c->radio,&c->mailbox);
        break;
    case XNOW_SESSION_VERIFY_STOCK:
        result=c->options.radio_guard(c->options.context,action);
        if(!result)result=xnow_sd8686_stock_verify();
        break;
    case XNOW_SESSION_CONFIGURE:
        result=c->options.radio_guard(c->options.context,action);
        if(!result)result=xnow_sd8686_channel_set(&c->radio,&c->session,c->options.channel);
        break;
    default:result=XNOW_ARGUMENT;break;
    }
    c->stepping=0;return complete(c,action,result);
}
void xnow_control_stop(struct xnow_control *c){
    if(!owner(c))return;
    xnow_session_stop(&c->session);xnow_sd8686_close(&c->radio);
}
int xnow_control_retry_restore(struct xnow_control *c){
    if(!owner(c)||c->uncertain||c->stepping||c->job.pid||c->manager.uncertain)return XNOW_UNCERTAIN;
    return xnow_session_retry_restore(&c->session);
}
struct xnow_mailbox *xnow_control_mailbox(struct xnow_control *c){
    return owner(c)&&!c->uncertain&&c->session.phase==XNOW_SESSION_READY&&c->radio.verified?&c->mailbox:0;
}
int xnow_control_finished(const struct xnow_control *c){
    return owner(c)&&!c->uncertain&&!c->job.pid&&!c->manager.held&&c->session.phase==XNOW_SESSION_DONE;
}
