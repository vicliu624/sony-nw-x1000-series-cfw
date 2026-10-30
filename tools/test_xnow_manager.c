#include "../runtime/platform/espnow/xnow_manager.h"
#include <assert.h>
#include <stdio.h>
static int state=4,clients,prepare_error,finish_error,guard_error;
static int capture_error;
static unsigned opens,finishes,disconnects,connects;
int cnmgr_init(void *callback,const void *info){assert(!callback&&!info);clients++;opens++;return 0;}
int cnmgr_get_state(void){return state;}
int cnmgr_get_target_connect_info(void *out){
    if(capture_error)return capture_error;
    for(unsigned i=0;i<1004;i++)((unsigned char *)out)[i]=(unsigned char)(i^0x5a);
    return 0;
}
int cnmgr_disconnect(void){assert(clients==1);disconnects++;state=3;return 0;}
int cnmgr_prepare_connect(void){assert(clients==1&&state==3);return prepare_error;}
int cnmgr_connect(const void *info){
    assert(info&&clients==1);
    for(unsigned i=0;i<1004;i++)assert(((const unsigned char *)info)[i]==(unsigned char)(i^0x5a));
    connects++;state=4;return 0;
}
int cnmgr_fin(void){finishes++;if(finish_error)return finish_error;assert(clients==1);clients--;return 0;}
static int guard(void *context,enum xnow_session_action action){(void)context;(void)action;return guard_error;}
static void execute(struct xnow_manager *m,struct xnow_session *s,enum xnow_session_action expected){
    assert(xnow_session_take(s)==expected);int result=xnow_manager_execute(m,s,0,guard);
    assert(!xnow_session_complete(s,expected,result));
}
static void fake_action(struct xnow_session *s,enum xnow_session_action expected){
    assert(xnow_session_take(s)==expected);assert(!xnow_session_complete(s,expected,0));
}
int main(void){
    struct xnow_manager m;struct xnow_session s;
    xnow_manager_init(&m);xnow_session_init(&s,1);
    assert(xnow_manager_execute(&m,&s,0,guard)==-1&&!opens);
    fake_action(&s,XNOW_SESSION_PREFLIGHT);
    execute(&m,&s,XNOW_SESSION_ACQUIRE);assert(clients==1&&m.held);
    execute(&m,&s,XNOW_SESSION_INSPECT);assert(s.was_connected);
    execute(&m,&s,XNOW_SESSION_DISCONNECT);assert(state==3&&disconnects==1);
    fake_action(&s,XNOW_SESSION_UNLOAD);fake_action(&s,XNOW_SESSION_LOAD_CANDIDATE);
    fake_action(&s,XNOW_SESSION_WAKE);fake_action(&s,XNOW_SESSION_VERIFY_CANDIDATE);fake_action(&s,XNOW_SESSION_INITIALIZE);
    fake_action(&s,XNOW_SESSION_CONFIGURE);assert(s.phase==XNOW_SESSION_READY&&clients==1);
    xnow_session_stop(&s);fake_action(&s,XNOW_SESSION_RESTORE_UNLOAD);
    fake_action(&s,XNOW_SESSION_LOAD_STOCK);fake_action(&s,XNOW_SESSION_RESTORE_WAKE);
    fake_action(&s,XNOW_SESSION_VERIFY_STOCK);fake_action(&s,XNOW_SESSION_RESTORE_INITIALIZE);
    execute(&m,&s,XNOW_SESSION_RECONNECT);assert(state==4&&connects==1&&clients==1);
    execute(&m,&s,XNOW_SESSION_RELEASE);assert(!clients&&!m.held&&finishes==1);
    for(unsigned i=0;i<1004;i++)assert(!m.current.bytes[i]);
    /* Rejected guards/owners must leave the retained stock client untouched. */
    xnow_manager_init(&m);xnow_session_init(&s,0);fake_action(&s,XNOW_SESSION_PREFLIGHT);
    execute(&m,&s,XNOW_SESSION_ACQUIRE);
    s.pending=XNOW_SESSION_DISCONNECT;s.was_connected=1;
    assert(xnow_manager_execute(&m,&s,0,guard)==-1&&disconnects==1);
    s.pending=XNOW_SESSION_INSPECT;m.owner++;
    assert(xnow_manager_execute(&m,&s,0,guard)==-1);m.owner--;
    m.executing=1;assert(xnow_manager_execute(&m,&s,0,guard)==-1);m.executing=0;
    s.allow_disconnect=1;capture_error=4;
    assert(xnow_manager_execute(&m,&s,0,guard)==XNOW_MANAGER_CONFIG_UNAVAILABLE&&!m.current_valid&&m.capture_result==4);
    capture_error=0;assert(xnow_manager_execute(&m,&s,0,guard)==4&&m.current_valid);
    s.phase=XNOW_SESSION_STOPPING;s.pending=XNOW_SESSION_RECONNECT;state=3;prepare_error=1;
    assert(xnow_manager_execute(&m,&s,0,guard)==1&&connects==1&&m.held);
    prepare_error=0;assert(!xnow_manager_execute(&m,&s,0,guard)&&connects==2);
    s.pending=XNOW_SESSION_RELEASE;guard_error=1;
    assert(xnow_manager_execute(&m,&s,0,guard)==-1&&finishes==1&&m.held);
    guard_error=0;assert(!xnow_manager_execute(&m,&s,0,guard)&&!clients);
    /* A failed fin is uncertain; never blindly issue it a second time. */
    xnow_manager_init(&m);xnow_session_init(&s,0);fake_action(&s,XNOW_SESSION_PREFLIGHT);
    execute(&m,&s,XNOW_SESSION_ACQUIRE);xnow_session_stop(&s);
    finish_error=1;execute(&m,&s,XNOW_SESSION_RELEASE);
    assert(m.uncertain&&m.held&&s.phase==XNOW_SESSION_REPAIR_REQUIRED);
    s.pending=XNOW_SESSION_RELEASE;assert(xnow_manager_execute(&m,&s,0,guard)==-1&&finishes==3);
    puts("XNOW manager: original API order, retained client, state checks and no duplicate fin passed (API effects substituted)");
    return 0;
}
