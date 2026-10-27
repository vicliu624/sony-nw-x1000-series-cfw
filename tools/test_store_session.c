#include "../runtime/store/session.h"
#include <assert.h>
#include <string.h>
struct fixture {struct hb_store_session *session;int calls,result;enum hb_store_action action;};
static int perform(void *context,enum hb_store_action action,volatile int *stop){
 struct fixture *f=context;assert(f->session->screen==HB_STORE_RUNNING);
 assert(!*stop);assert(hb_store_session_request(f->session,HB_STORE_INSTALL)==-1);
 assert(hb_store_session_confirm(f->session)==-1);
 f->calls++;f->action=action;return f->result;
}
int main(void){
 struct hb_store_session s;struct fixture f={&s,0,0,HB_STORE_INSTALL};
 struct hb_store_backend backend={&f,perform};
 assert(!hb_store_session_init(&s,backend));assert(!f.calls);
 assert(hb_store_session_confirm(&s)==-1);
 assert(!hb_store_session_request(&s,HB_STORE_INSTALL));assert(!f.calls);
 assert(!hb_store_session_back(&s));assert(!f.calls);
 assert(!hb_store_session_request(&s,HB_STORE_INSTALL));assert(!hb_store_session_confirm(&s));
 assert(f.calls==1&&!strcmp(hb_store_session_message(&s),"Installed"));
 for(int result=HB_INSTALL_INVALID;result<=HB_INSTALLED_CLEANUP_PENDING;result++){
  assert(!hb_store_session_init(&s,backend));f.result=result;
  assert(!hb_store_session_request(&s,HB_STORE_INSTALL));assert(!hb_store_session_confirm(&s));
  assert(s.result==result&&s.screen==HB_STORE_RESULT);
  if(result==HB_RECOVERY_REQUIRED||result==HB_INSTALLED_CLEANUP_PENDING){
   assert(hb_store_session_request(&s,HB_STORE_INSTALL)==-1);
   assert(!hb_store_session_back(&s));assert(hb_store_session_request(&s,HB_STORE_INSTALL)==-1);
   assert(!hb_store_session_request(&s,HB_STORE_RECOVER));f.result=0;
   assert(!hb_store_session_confirm(&s));assert(f.action==HB_STORE_RECOVER);
   assert(!hb_store_session_request(&s,HB_STORE_INSTALL));
  }
 }
 assert(!hb_store_session_init(&s,backend));f.result=999;
 assert(!hb_store_session_request(&s,HB_STORE_CANCEL_IDLE));
 assert(!strcmp(hb_store_session_message(&s),"Cancel idle installation records?"));
 assert(!hb_store_session_confirm(&s));assert(s.result==HB_RECOVERY_REQUIRED);
 return 0;
}
