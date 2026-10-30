#include "../runtime/platform/espnow/xnow_session.h"
#include <assert.h>
#include <stdio.h>
static void complete(struct xnow_session *s,enum xnow_session_action expected,int result) {
    assert(xnow_session_take(s)==expected);
    assert(xnow_session_take(s)==XNOW_SESSION_NONE);
    assert(xnow_session_complete(s,XNOW_SESSION_NONE,0)==-1);
    assert(!xnow_session_complete(s,expected,result));
    assert(xnow_session_complete(s,expected,result)==-1);
}
static void startup(struct xnow_session *s,int connected) {
    xnow_session_init(s,1);
    complete(s,XNOW_SESSION_PREFLIGHT,0);complete(s,XNOW_SESSION_ACQUIRE,0);
    complete(s,XNOW_SESSION_INSPECT,connected?4:3);
    if(connected)complete(s,XNOW_SESSION_DISCONNECT,0);
    complete(s,XNOW_SESSION_UNLOAD,0);complete(s,XNOW_SESSION_LOAD_CANDIDATE,0);
    complete(s,XNOW_SESSION_WAKE,0);
    complete(s,XNOW_SESSION_VERIFY_CANDIDATE,0);complete(s,XNOW_SESSION_INITIALIZE,0);complete(s,XNOW_SESSION_CONFIGURE,0);
    assert(s->phase==XNOW_SESSION_READY&&s->lease&&s->changed);
}
static void restore(struct xnow_session *s) {
    assert(s->phase==XNOW_SESSION_STOPPING);
    complete(s,XNOW_SESSION_RESTORE_UNLOAD,0);complete(s,XNOW_SESSION_LOAD_STOCK,0);
    complete(s,XNOW_SESSION_RESTORE_WAKE,0);complete(s,XNOW_SESSION_VERIFY_STOCK,0);
    complete(s,XNOW_SESSION_RESTORE_INITIALIZE,0);
    if(s->was_connected)complete(s,XNOW_SESSION_RECONNECT,0);
    complete(s,XNOW_SESSION_RELEASE,0);
    assert(s->phase==XNOW_SESSION_DONE&&!s->lease&&!s->changed);
}
int main(void) {
    struct xnow_session s;
    for(int connected=0;connected<2;connected++){
        startup(&s,connected);xnow_session_stop(&s);restore(&s);
    }
    /* Borrowed connection cannot be silently disconnected. */
    xnow_session_init(&s,0);complete(&s,XNOW_SESSION_PREFLIGHT,0);
    complete(&s,XNOW_SESSION_ACQUIRE,0);complete(&s,XNOW_SESSION_INSPECT,4);
    assert(s.failure&&!s.changed);complete(&s,XNOW_SESSION_RELEASE,0);
    /* Failure/cancellation at every startup stage, including partial unload. */
    for(int cancelled=0;cancelled<2;cancelled++)for(int target=XNOW_SESSION_PREFLIGHT;target<=XNOW_SESSION_CONFIGURE;target++){
        xnow_session_init(&s,1);
        while(s.phase==XNOW_SESSION_STARTING){
            enum xnow_session_action action=xnow_session_take(&s);
            int result=action==XNOW_SESSION_INSPECT?4:0;
            assert(action!=XNOW_SESSION_NONE);
            if(action==(enum xnow_session_action)target){
                if(cancelled){xnow_session_stop(&s);assert(s.pending==action);}
                else result=-7;
            }
            assert(!xnow_session_complete(&s,action,result));
        }
        assert(s.phase!=XNOW_SESSION_READY);
        if(s.changed)restore(&s);
        else if(s.lease)complete(&s,XNOW_SESSION_RELEASE,0);
        assert(s.phase==XNOW_SESSION_DONE);
    }
    /* Do not discard lease or claim recovery if any restoration step fails. */
    for(int target=XNOW_SESSION_RESTORE_UNLOAD;target<=XNOW_SESSION_RELEASE;target++){
        startup(&s,1);xnow_session_stop(&s);
        while(s.phase==XNOW_SESSION_STOPPING){
            enum xnow_session_action action=xnow_session_take(&s);
            assert(action!=XNOW_SESSION_NONE);
            assert(!xnow_session_complete(&s,action,action==(enum xnow_session_action)target?-9:0));
        }
        assert(s.phase==XNOW_SESSION_REPAIR_REQUIRED&&s.lease&&s.restore_failure==-9);
        assert(xnow_session_take(&s)==XNOW_SESSION_NONE);
        assert(!xnow_session_retry_restore(&s));restore(&s);
    }
    puts("XNOW session: ownership, serialized completion, cancellation drain, startup faults and restoration faults passed");
    return 0;
}
