#include "../../runtime/platform/services/session.h"
#include <assert.h>
#include <stdio.h>
static int release(void *context,struct xw_session_handle h,uint32_t reason){(void)context;(void)h;assert(reason==XW_SESSION_USB);return 0;}
static int fault(void *context,struct xw_session_handle h,uint32_t reason){(void)context;(void)h;(void)reason;return -1;}
int main(void){
 static struct xw_session_manager m;struct xw_session_handle a,b,next={0};struct xw_session_snapshot view;
 assert(!xw_sessions_init(&m,1,7)&&!xw_session_open(&m,1,1,&a)&&!xw_session_open(&m,2,2,&b));
 assert(xw_sessions_drained(&m)==XW_SESSION_DENIED);
 assert(xw_sessions_quiesce(&m,XW_SESSION_USB)==XW_SESSION_PENDING&&!m.accepting);
 assert(xw_session_open(&m,1,1,&next)==XW_SESSION_DENIED&&!next.serial);
 uint64_t epoch=99;assert(xw_session_admit(&m,a,1,&epoch)==XW_SESSION_DENIED&&epoch==99);
 assert(!xw_session_read(&m,a,&view)&&view.state==XW_SESSION_CLOSING&&view.reason==XW_SESSION_USB&&view.epoch==2);
 assert(xw_sessions_quiesce(&m,XW_SESSION_SLEEP)==XW_SESSION_PENDING);
 assert(!xw_session_read(&m,a,&view)&&view.epoch==2&&view.reason==XW_SESSION_USB);
 assert(xw_sessions_resume(&m)==XW_SESSION_PENDING&&!m.accepting);
 assert(!xw_session_close_step(&m,a,release,0)&&xw_sessions_drained(&m)==XW_SESSION_PENDING);
 assert(!xw_session_close_step(&m,b,release,0)&&!xw_sessions_drained(&m));
 assert(!m.accepting);assert(!xw_sessions_resume(&m)&&m.accepting);
 assert(!xw_session_open(&m,1,1,&next)&&next.serial>b.serial);
 assert(xw_session_admit(&m,a,1,&epoch)==XW_SESSION_STALE);
 assert(xw_sessions_quiesce(&m,XW_SESSION_USB)==XW_SESSION_PENDING);
 assert(xw_session_close_step(&m,next,fault,0)==XW_SESSION_FAULT);
 assert(xw_sessions_drained(&m)==XW_SESSION_FAULT&&xw_sessions_resume(&m)==XW_SESSION_FAULT&&!m.accepting);
 puts("Global quiesce: admission stop, all grants revoked, idempotent epochs, drain-before-resume and retained faults passed");return 0;
}
