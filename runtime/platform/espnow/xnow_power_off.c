#include "xnow_power_off.h"
#include "xnow_mailbox.h"
#include "../wireless/radio_modules.h"
#include <unistd.h>
extern int cnmgr_get_state(void);
extern int cnmgr_power_off(void);
int xnow_manager_power_off(struct xnow_manager *m,const struct xnow_session *s,
                           void *context,int (*exclusive)(void *)){
 if(!m||!s||!exclusive)return XNOW_ARGUMENT;
 if(m->owner!=(int)getpid()||m->executing||m->uncertain||!m->held||!s->lease||
    s->phase!=XNOW_SESSION_STOPPING||s->pending!=XNOW_SESSION_RELEASE||s->next!=XNOW_SESSION_NONE)
  return XNOW_RADIO_REJECTED;
 m->executing=1;int result=XNOW_RADIO_REJECTED;
 if(exclusive(context)!=1)goto done;
 int state=cnmgr_get_state();
 /* No disconnect, cancel, reconnection or implicit power-on. An active or
  * transitional stock Wi-Fi client must be handled by its original owner. */
 if(state!=2&&state!=3)goto done;
 if(exclusive(context)!=1)goto done;
 if(state==2){
  if(xw_wireless_modules_unloaded()!=1||exclusive(context)!=1){m->uncertain=1;result=XNOW_UNCERTAIN;}
  else result=0;
  goto done;
 }
 if(cnmgr_power_off()||cnmgr_get_state()!=2||xw_wireless_modules_unloaded()!=1||exclusive(context)!=1){
  m->uncertain=1;result=XNOW_UNCERTAIN;goto done;
 }
 result=0;
done:m->executing=0;return result;
}
