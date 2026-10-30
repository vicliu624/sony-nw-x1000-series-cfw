#include "xnow_session.h"
#include <string.h>
static void cleanup(struct xnow_session *s) {
    s->phase=XNOW_SESSION_STOPPING;
    s->next=s->changed?XNOW_SESSION_RESTORE_UNLOAD:
        s->lease?XNOW_SESSION_RELEASE:XNOW_SESSION_NONE;
    if(s->next==XNOW_SESSION_NONE)s->phase=XNOW_SESSION_DONE;
}
void xnow_session_init(struct xnow_session *s,unsigned allow_disconnect) {
    memset(s,0,sizeof(*s));s->allow_disconnect=!!allow_disconnect;
    s->phase=XNOW_SESSION_STARTING;s->next=XNOW_SESSION_PREFLIGHT;
}
enum xnow_session_action xnow_session_take(struct xnow_session *s) {
    enum xnow_session_action action;
    if(s->pending||s->phase==XNOW_SESSION_REPAIR_REQUIRED)return XNOW_SESSION_NONE;
    action=s->next;s->next=XNOW_SESSION_NONE;s->pending=action;
    /* Even a failed mutating request may have partially changed the radio. */
    if(action==XNOW_SESSION_DISCONNECT||action==XNOW_SESSION_UNLOAD)s->changed=1;
    return action;
}
int xnow_session_complete(struct xnow_session *s,enum xnow_session_action action,int result) {
    if(action==XNOW_SESSION_NONE||s->pending!=action)return -1;
    s->pending=XNOW_SESSION_NONE;
    if(action==XNOW_SESSION_ACQUIRE&&result==0)s->lease=1;
    if(action==XNOW_SESSION_INSPECT) {
        if(result==4)s->was_connected=1;
        result=(result==3||(result==4&&s->allow_disconnect))?0:-1;
    }
    if(result!=0) {
        if(s->phase==XNOW_SESSION_STOPPING) {
            s->restore_failure=result;s->phase=XNOW_SESSION_REPAIR_REQUIRED;
            return 0;
        }
        s->failure=result;cleanup(s);return 0;
    }
    if(s->cancelled&&s->phase==XNOW_SESSION_STARTING){cleanup(s);return 0;}
    switch(action) {
    case XNOW_SESSION_PREFLIGHT:s->next=XNOW_SESSION_ACQUIRE;break;
    case XNOW_SESSION_ACQUIRE:s->next=XNOW_SESSION_INSPECT;break;
    case XNOW_SESSION_INSPECT:s->next=s->was_connected?XNOW_SESSION_DISCONNECT:XNOW_SESSION_UNLOAD;break;
    case XNOW_SESSION_DISCONNECT:s->next=XNOW_SESSION_UNLOAD;break;
    case XNOW_SESSION_UNLOAD:s->next=XNOW_SESSION_LOAD_CANDIDATE;break;
    case XNOW_SESSION_LOAD_CANDIDATE:s->next=XNOW_SESSION_WAKE;break;
    case XNOW_SESSION_WAKE:s->next=XNOW_SESSION_VERIFY_CANDIDATE;break;
    case XNOW_SESSION_VERIFY_CANDIDATE:s->next=XNOW_SESSION_INITIALIZE;break;
    case XNOW_SESSION_INITIALIZE:s->next=XNOW_SESSION_CONFIGURE;break;
    case XNOW_SESSION_CONFIGURE:s->phase=XNOW_SESSION_READY;break;
    case XNOW_SESSION_RESTORE_UNLOAD:s->next=XNOW_SESSION_LOAD_STOCK;break;
    case XNOW_SESSION_LOAD_STOCK:s->next=XNOW_SESSION_RESTORE_WAKE;break;
    case XNOW_SESSION_RESTORE_WAKE:s->next=XNOW_SESSION_VERIFY_STOCK;break;
    case XNOW_SESSION_VERIFY_STOCK:s->next=XNOW_SESSION_RESTORE_INITIALIZE;break;
    case XNOW_SESSION_RESTORE_INITIALIZE:s->next=s->was_connected?XNOW_SESSION_RECONNECT:XNOW_SESSION_RELEASE;break;
    case XNOW_SESSION_RECONNECT:s->next=XNOW_SESSION_RELEASE;break;
    case XNOW_SESSION_RELEASE:s->lease=0;s->changed=0;s->phase=XNOW_SESSION_DONE;break;
    default:return -1;
    }
    return 0;
}
void xnow_session_stop(struct xnow_session *s) {
    s->cancelled=1;
    if(!s->pending&&(s->phase==XNOW_SESSION_STARTING||s->phase==XNOW_SESSION_READY))cleanup(s);
}
int xnow_session_retry_restore(struct xnow_session *s) {
    if(s->phase!=XNOW_SESSION_REPAIR_REQUIRED||s->pending)return -1;
    s->restore_failure=0;cleanup(s);return 0;
}
