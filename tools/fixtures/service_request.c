#include "../../runtime/platform/services/request.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
int main(void){
 static struct xw_session_manager m;static struct xw_request_ledger l;
 struct xw_session_handle h;struct xw_request_record r,old;
 assert(!xw_sessions_init(&m,12,1)&&!xw_session_open(&m,1,1,&h)&&!xw_requests_init(&l,&m,h));
 assert(!xw_request_submit(&l,&m,1,1,"next",4));
 assert(xw_request_submit(&l,&m,1,1,"next",4)==XW_REQUEST_DUPLICATE);
 assert(xw_request_submit(&l,&m,1,1,"prev",4)==XW_REQUEST_CONFLICT);
 assert(!xw_request_start(&l,&m,1)&&xw_request_start(&l,&m,1)==XW_SESSION_DENIED);
 assert(xw_request_cancel(&l,1)==XW_SESSION_PENDING);
 assert(!xw_request_finish(&l,1,123)&&!xw_request_read(&l,1,&r)&&r.result==123);
 for(uint64_t id=2;id<=10;id++)assert(!xw_request_submit(&l,&m,id,1,"next",4)&&!xw_request_cancel(&l,id));
 old=r;assert(xw_request_read(&l,1,&r)==XW_REQUEST_UNKNOWN&&!memcmp(&r,&old,sizeof r));
 assert(xw_request_submit(&l,&m,1,1,"next",4)==XW_REQUEST_UNKNOWN);
 assert(!xw_request_submit(&l,&m,11,1,"next",4));
 m.busy=1;assert(xw_request_start(&l,&m,11)==XW_SESSION_BUSY);m.busy=0;
 assert(!xw_request_read(&l,11,&r)&&r.state==XW_REQUEST_QUEUED);
 assert(xw_session_revoke(&m,h,XW_SESSION_USB)==XW_SESSION_PENDING);
 assert(xw_request_start(&l,&m,11)==XW_SESSION_DENIED);
 assert(!xw_request_read(&l,11,&r)&&r.state==XW_REQUEST_CANCELLED);
 puts("Request dedup, payload conflict, no replay after eviction, running cancellation and revoked dispatch passed");return 0;
}
