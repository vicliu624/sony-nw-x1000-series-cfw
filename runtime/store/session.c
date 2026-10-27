#include "session.h"
int hb_store_session_init(struct hb_store_session *s,struct hb_store_backend backend){
 if(!s||!backend.perform)return -1;
 s->backend=backend;s->screen=HB_STORE_LIST;s->pending=HB_STORE_INSTALL;
 s->result=0;s->has_result=0;s->executing=0;s->stop=0;return 0;
}
int hb_store_session_request(struct hb_store_session *s,enum hb_store_action action){
 if(!s||action<HB_STORE_INSTALL||action>HB_STORE_CANCEL_IDLE||
    (s->screen!=HB_STORE_LIST&&s->screen!=HB_STORE_RESULT))return -1;
 /* An unresolved transaction must be reviewed before another installation. */
 if(action==HB_STORE_INSTALL&&s->has_result&&
    (s->result==HB_RECOVERY_REQUIRED||s->result==HB_INSTALLED_CLEANUP_PENDING))return -1;
 s->pending=action;s->screen=HB_STORE_CONFIRM;return 0;
}
int hb_store_session_back(struct hb_store_session *s){
 if(!s)return -1;
 if(s->screen==HB_STORE_CONFIRM||s->screen==HB_STORE_RESULT){s->screen=HB_STORE_LIST;return 0;}
 return -1;
}
int hb_store_session_begin(struct hb_store_session *s){
 if(!s||s->screen!=HB_STORE_CONFIRM)return -1;
 s->stop=0;s->screen=HB_STORE_RUNNING;return 0;
}
int hb_store_session_execute(struct hb_store_session *s){
 if(!s||s->screen!=HB_STORE_RUNNING||s->executing)return -1;
 s->executing=1;
 int result=s->backend.perform(s->backend.context,s->pending,&s->stop);
 if(result<HB_INSTALL_INVALID||result>HB_INSTALLED_CLEANUP_PENDING)result=HB_RECOVERY_REQUIRED;
 s->result=result;s->has_result=1;s->executing=0;s->screen=HB_STORE_RESULT;return 0;
}
int hb_store_session_confirm(struct hb_store_session *s){
 return hb_store_session_begin(s)?-1:hb_store_session_execute(s);
}
const char *hb_store_session_message(const struct hb_store_session *s){
 if(!s)return "Store unavailable";
 if(s->screen==HB_STORE_CONFIRM){
  if(s->pending==HB_STORE_RECOVER)return "Recover interrupted installation?";
  if(s->pending==HB_STORE_CANCEL_IDLE)return "Cancel idle installation records?";
  return "Install selected package?";
 }
 if(s->screen==HB_STORE_RUNNING)return "Working...";
 if(!s->has_result)return "Select a package";
 switch(s->result){
 case HB_INSTALLED:return s->pending==HB_STORE_INSTALL?"Installed":"Operation complete";
 case HB_INSTALLED_CLEANUP_PENDING:return "Cleanup needed. Choose Recover";
 case HB_INSTALL_CANCELLED:return "Cancelled";
 case HB_INSTALL_NO_SPACE:return "Not enough free space";
 case HB_INSTALL_INVALID:return "Package or path invalid";
 case HB_RECOVERY_REQUIRED:return "Recovery needed. Keep files";
 default:return "Operation failed";
 }
}
