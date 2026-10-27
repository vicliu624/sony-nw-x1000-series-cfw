#include "session_local.h"
#include "install_posix.h"
static int copy(char *out,const char *input,unsigned capacity){
 if(!input)return -1;
 unsigned n=0;while(n<capacity&&input[n])n++;
 if(!n||n==capacity)return -1;
 for(unsigned i=0;i<=n;i++)out[i]=input[i];
 return 0;
}
static int perform(void *context,enum hb_store_action action,volatile int *stop){
 struct hb_store_local_session *s=context;
 if(s->external_stop)stop=s->external_stop;
 if(stop&&*stop)return HB_INSTALL_CANCELLED;
 if(action==HB_STORE_INSTALL){
  if(s->has_expected_identity)return hb_store_install_local_expected(s->apps_root,s->source,s->id,s->reserve,stop,s->expected_identity);
  return hb_store_install_local(s->apps_root,s->source,s->id,s->reserve,stop);
 }
 if(action==HB_STORE_RECOVER)return hb_store_recover_local(s->apps_root,s->id,stop);
 if(action==HB_STORE_CANCEL_IDLE)return hb_store_cancel_idle_local(s->apps_root,s->id,stop);
 return HB_RECOVERY_REQUIRED;
}
int hb_store_local_session_init(struct hb_store_local_session *s,const char *root,
 const char *source,const char *id,unsigned long long reserve){
 struct hb_store_local_session value={0};
 if(!s||copy(value.apps_root,root,sizeof value.apps_root)||
    copy(value.source,source,sizeof value.source)||copy(value.id,id,sizeof value.id))return -1;
 for(unsigned i=0;value.id[i];i++)if(!((value.id[i]>='a'&&value.id[i]<='z')||
   (value.id[i]>='0'&&value.id[i]<='9')||(i&&value.id[i]=='-')))return -1;
 value.reserve=reserve;
 struct hb_store_backend backend={s,perform};
 if(hb_store_session_init(&value.interaction,backend))return -1;
 *s=value;return 0;
}
