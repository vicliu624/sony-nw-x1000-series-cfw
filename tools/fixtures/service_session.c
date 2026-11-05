#include "../../runtime/platform/services/session.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static struct xw_session_manager manager;
static unsigned calls;
static int release(void *context,struct xw_session_handle h,uint32_t reason){
 assert(context==&manager&&reason==XW_SESSION_USB);uint64_t epoch=99;
 assert(xw_session_admit(&manager,h,1,&epoch)==XW_SESSION_BUSY&&epoch==99);
 return ++calls==1?XW_SESSION_PENDING:0;
}
static int fail(void *c,struct xw_session_handle h,uint32_t r){(void)c;(void)h;(void)r;return -1;}
int main(void){
 struct xw_session_handle h[5]={{0}},old;struct xw_session_snapshot before,after;
 assert(!xw_sessions_init(&manager,7,3));assert(xw_sessions_init(&manager,8,3)==XW_SESSION_BUSY);
 assert(xw_session_open(&manager,2,1,&h[0])==XW_SESSION_DENIED&&!h[0].serial);
 for(unsigned i=0;i<4;i++)assert(!xw_session_open(&manager,1,1,&h[i]));
 assert(xw_session_open(&manager,1,1,&h[4])==XW_SESSION_BUSY);
 uint64_t epoch=0;assert(!xw_session_admit(&manager,h[0],1,&epoch)&&epoch==1);
 assert(!xw_session_read(&manager,h[0],&before));
 assert(xw_session_revoke(&manager,h[0],XW_SESSION_USB)==XW_SESSION_PENDING);
 assert(xw_session_admit(&manager,h[0],1,&epoch)==XW_SESSION_DENIED&&epoch==1);
 assert(!xw_session_read(&manager,h[0],&after)&&after.epoch==2&&!after.grants);
 assert(xw_session_close_step(&manager,h[0],release,&manager)==XW_SESSION_PENDING);
 assert(!xw_session_close_step(&manager,h[0],release,&manager));
 assert(!xw_session_close_step(&manager,h[0],release,&manager)&&calls==2);
 old=h[0];assert(!xw_session_open(&manager,1,1,&h[0])&&old.serial!=h[0].serial);
 assert(!xw_session_close_query(&manager,old,&after)&&after.state==XW_SESSION_CLOSED&&after.reason==XW_SESSION_USB);
 before=after;assert(xw_session_read(&manager,old,&after)==XW_SESSION_STALE&&!memcmp(&before,&after,sizeof after));
 old=h[0];old.generation++;assert(xw_session_read(&manager,old,&after)==XW_SESSION_STALE);
 assert(xw_session_revoke(&manager,h[0],XW_SESSION_SLEEP)==XW_SESSION_PENDING);
 assert(xw_session_close_step(&manager,h[0],fail,0)==XW_SESSION_FAULT);
 assert(xw_session_close_step(&manager,h[0],release,&manager)==XW_SESSION_FAULT);
 assert(xw_session_open(&manager,1,1,&h[4])==XW_SESSION_BUSY);
 assert(!xw_session_close_query(&manager,h[0],&after)&&after.state==XW_SESSION_FAILED);
 struct xw_session_handle expired=h[1];
 for(unsigned i=0;i<5;i++){
  assert(xw_session_revoke(&manager,h[1],XW_SESSION_USB)==XW_SESSION_PENDING);
  assert(!xw_session_close_step(&manager,h[1],release,&manager));
  assert(!xw_session_open(&manager,1,1,&h[1]));
 }
 before=after;assert(xw_session_close_query(&manager,expired,&after)==XW_SESSION_STALE&&!memcmp(&before,&after,sizeof after));
 puts("Session grants, capacity, stale handles, revoke, pending close, reentry and retained faults passed");return 0;
}
