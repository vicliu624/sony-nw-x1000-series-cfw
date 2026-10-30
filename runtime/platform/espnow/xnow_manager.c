#include "xnow_manager.h"
#include <unistd.h>
#include <string.h>
extern int cnmgr_init(void *,const void *);
extern int cnmgr_get_state(void);
extern int cnmgr_get_target_connect_info(void *);
extern int cnmgr_disconnect(void);
extern int cnmgr_prepare_connect(void);
extern int cnmgr_connect(const void *);
extern int cnmgr_fin(void);
void xnow_manager_init(struct xnow_manager *m) {
    memset(m,0,sizeof(*m));m->owner=(int)getpid();m->capture_result=-1;
}
static void forget_current(struct xnow_manager *m){
    volatile unsigned char *p=m->current.bytes;
    for(unsigned i=0;i<XNOW_CURRENT_CONFIG_BYTES;i++)p[i]=0;
    m->current_valid=0;
}
int xnow_manager_execute(struct xnow_manager *m,const struct xnow_session *s,void *context,
                          int (*guard)(void *,enum xnow_session_action)) {
    int result=-1,state;enum xnow_session_action action;
    if(!m||!s||!guard||m->executing||m->uncertain||m->owner!=(int)getpid())return -1;
    action=s->pending;
    if(action==XNOW_SESSION_ACQUIRE) {
        if(m->held||s->lease||s->phase!=XNOW_SESSION_STARTING)return -1;
    }else {
        if(!m->held||!s->lease)return -1;
        if(action==XNOW_SESSION_INSPECT||action==XNOW_SESSION_DISCONNECT){
            if(s->phase!=XNOW_SESSION_STARTING)return -1;
            if(action==XNOW_SESSION_DISCONNECT&&(!s->allow_disconnect||!s->was_connected))return -1;
        }else if(action==XNOW_SESSION_RECONNECT||action==XNOW_SESSION_RELEASE){
            if(s->phase!=XNOW_SESSION_STOPPING)return -1;
        }else return -1;
    }
    m->executing=1;
    if(guard(context,action))goto done;
    switch(action){
    case XNOW_SESSION_ACQUIRE:
        result=cnmgr_init(0,0);
        if(!result)m->held=1;else m->uncertain=1;
        break;
    case XNOW_SESSION_INSPECT:
        result=cnmgr_get_state();
        if(result==4&&s->allow_disconnect){
            forget_current(m);m->capture_result=cnmgr_get_target_connect_info(m->current.bytes);
            if(!m->capture_result)m->current_valid=1;
            else {forget_current(m);result=XNOW_MANAGER_CONFIG_UNAVAILABLE;}
        }
        break;
    case XNOW_SESSION_DISCONNECT:
        if(!m->current_valid){result=XNOW_MANAGER_CONFIG_UNAVAILABLE;break;}
        state=cnmgr_get_state();
        if(state==3){result=0;break;}
        if(state!=4)break;
        result=cnmgr_disconnect();
        if(!result&&cnmgr_get_state()!=3)result=-1;
        break;
    case XNOW_SESSION_RECONNECT:
        state=cnmgr_get_state();
        if(state==4){result=0;break;}
        if(state!=3)break;
        if(!m->current_valid){result=XNOW_MANAGER_CONFIG_UNAVAILABLE;break;}
        result=cnmgr_prepare_connect();
        if(!result)result=cnmgr_connect(m->current.bytes);
        if(!result&&cnmgr_get_state()!=4)result=-1;
        break;
    case XNOW_SESSION_RELEASE:
        forget_current(m);
        result=cnmgr_fin();
        if(!result)m->held=0;else m->uncertain=1;
        break;
    default:break;
    }
done:m->executing=0;return result;
}
