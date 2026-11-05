#include "../runtime/platform/espnow/xnow_power_off.h"
#include "../runtime/platform/espnow/xnow_mailbox.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static int state,after,power_result,permission,lose_at;
static unsigned reads,power_calls,guards;
static int modules_clear;
int xw_wireless_modules_unloaded(void){return modules_clear;}
static struct xnow_manager manager;
static struct xnow_session session;
int cnmgr_get_state(void){reads++;return state;}
int cnmgr_power_off(void){power_calls++;state=after;return power_result;}
static int exclusive(void *context){
 assert(context==&manager&&manager.executing);guards++;
 assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED);
 return lose_at&&(int)guards>=lose_at?0:permission;
}
static void reset(void){
 memset(&manager,0,sizeof manager);memset(&session,0,sizeof session);
 manager.owner=(int)getpid();manager.held=1;session.lease=1;
 session.phase=XNOW_SESSION_STOPPING;session.pending=XNOW_SESSION_RELEASE;
 state=3;after=2;power_result=0;permission=1;lose_at=0;reads=power_calls=guards=0;
 modules_clear=1;
}
int main(void){
 reset();assert(!xnow_manager_power_off(&manager,&session,&manager,exclusive));
 assert(power_calls==1&&reads==2&&guards==3&&manager.held&&!manager.uncertain&&!manager.executing);
 assert(session.pending==XNOW_SESSION_RELEASE&&session.lease);
 assert(!xnow_manager_power_off(&manager,&session,&manager,exclusive)&&power_calls==1);
 reset();permission=0;assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED);
 assert(!reads&&!power_calls&&!manager.uncertain);
 reset();permission=2;assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED&&!reads);
 for(int current=-1;current<=8;current++)if(current!=2&&current!=3){
  reset();state=current;assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED);
  assert(!power_calls&&!manager.uncertain&&manager.held);
 }
 for(int invalid=0;invalid<7;invalid++){
  reset();if(invalid==0)manager.owner++;if(invalid==1)manager.held=0;if(invalid==2)manager.executing=1;
  if(invalid==3)manager.uncertain=1;if(invalid==4)session.lease=0;
  if(invalid==5)session.phase=XNOW_SESSION_READY;if(invalid==6)session.pending=XNOW_SESSION_RECONNECT;
  assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED);
  assert(!reads&&!guards&&!power_calls);
 }
 reset();lose_at=2;assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED&&!power_calls);
 for(int failure=0;failure<4;failure++){
  reset();if(!failure)power_result=1;if(failure==1)after=3;if(failure==2)lose_at=3;
  if(failure==3)modules_clear=0;
  assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_UNCERTAIN);
  assert(manager.uncertain&&manager.held&&!manager.executing&&power_calls==1);
  assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_RADIO_REJECTED&&power_calls==1);
 }
 reset();state=2;modules_clear=0;
 assert(xnow_manager_power_off(&manager,&session,&manager,exclusive)==XNOW_UNCERTAIN&&manager.uncertain&&manager.held&&!power_calls);
 reset();assert(xnow_manager_power_off(0,&session,&manager,exclusive)==XNOW_ARGUMENT);
 assert(xnow_manager_power_off(&manager,0,&manager,exclusive)==XNOW_ARGUMENT);
 assert(xnow_manager_power_off(&manager,&session,&manager,0)==XNOW_ARGUMENT);
 assert(!power_calls&&!reads);puts("XNOW_POWER_OFF_PASS");return 0;
}
