#include "../runtime/store/session_local.h"
#include "../runtime/store/install_posix.h"
#include <assert.h>
#include <string.h>
static int calls;
static volatile int *expected_stop;
int hb_store_install_local_expected(const char *root,const char *source,const char *id,unsigned long long reserve,volatile int *stop,const unsigned char *identity){
 (void)identity;return hb_store_install_local(root,source,id,reserve,stop);
}
int hb_store_install_local(const char *root,const char *source,const char *id,unsigned long long reserve,volatile int *stop){
 assert(!strcmp(root,"/apps")&&!strcmp(source,"/package")&&!strcmp(id,"demo")&&reserve==4096&&!*stop);
 if(expected_stop)assert(stop==expected_stop);
 calls++;return 0;
}
int hb_store_recover_local(const char *root,const char *id,volatile int *stop){
 assert(!strcmp(root,"/apps")&&!strcmp(id,"demo")&&!*stop);calls++;return 0;
}
int hb_store_cancel_idle_local(const char *root,const char *id,volatile int *stop){
 return hb_store_recover_local(root,id,stop);
}
int main(void){
 struct hb_store_local_session s;char root[]="/apps",source[]="/package",id[]="demo";
 assert(!hb_store_local_session_init(&s,root,source,id,4096));assert(!calls);
 root[1]='X';source[1]='X';id[0]='X';
 for(int action=HB_STORE_INSTALL;action<=HB_STORE_CANCEL_IDLE;action++){
  assert(!hb_store_session_request(&s.interaction,(enum hb_store_action)action));
  assert(calls==action);assert(!hb_store_session_confirm(&s.interaction));
  assert(calls==action+1&&s.interaction.result==0);
 }
 volatile int external=0;s.external_stop=&external;expected_stop=&external;
 assert(!hb_store_session_request(&s.interaction,HB_STORE_INSTALL));
 assert(!hb_store_session_confirm(&s.interaction)&&calls==4);
 external=1;
 assert(!hb_store_session_request(&s.interaction,HB_STORE_INSTALL));
 assert(!hb_store_session_confirm(&s.interaction)&&calls==4&&s.interaction.result==HB_INSTALL_CANCELLED);
 struct hb_store_local_session before=s;
 assert(hb_store_local_session_init(&s,"/apps","/package","../demo",4096)==-1);
 assert(!memcmp(&before,&s,sizeof s));
 char oversized[513];memset(oversized,'x',512);oversized[512]=0;
 assert(hb_store_local_session_init(&s,oversized,"/package","demo",4096)==-1);
 assert(!memcmp(&before,&s,sizeof s));return 0;
}
