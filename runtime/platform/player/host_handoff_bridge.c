#include "host_handoff_bridge.h"
#include "host_prepare_bridge.h"
#include "host_managed_service.h"
#include "stock_prepare_view.h"
#include "wireless_host.h"
extern unsigned long pthread_self(void);
static struct xw_stock_prepare_view view;
static uint64_t epoch;
static unsigned long owner;
/* WAIT, CALLING, FORWARDED, FAULT, RESTORING, REARM; deny new handoff entry
 * until qualified activation and radio release have completed. */
static unsigned state,busy;
static uint32_t restore_client,restore_sequence;
static int restore_view(unsigned client_state,unsigned command){
 if(xw_stock_prepare_code_check())return 0;
 uintptr_t client=((uintptr_t (*)(void))(uintptr_t)0x265510u)();
 if(!client||(client&3u)||client!=restore_client)return 0;
 const volatile uint32_t *root=(const volatile uint32_t *)(uintptr_t)0x613e60u;
 const volatile uint32_t *apf=(const volatile uint32_t *)client;
 return root[1]==command&&root[0x2c/4]==0x66efe8u&&
  *(const volatile uint32_t *)(uintptr_t)0x66efe8u==0&&apf[1]==client_state;
}
int xw_player_handoff_resume_begin(uint32_t root,unsigned long original_owner){
 if(state==0)return 0;
 if(state!=3||busy||root!=0x613e60u||original_owner!=owner||pthread_self()!=owner)return XW_PREPARE_BRIDGE_HANDLED;
 if(xw_stock_prepare_code_check()){state=4;return XW_PREPARE_BRIDGE_HANDLED;}
 restore_client=(uint32_t)((uintptr_t (*)(void))(uintptr_t)0x265510u)();
 if(!restore_view(1,6)){state=4;return XW_PREPARE_BRIDGE_HANDLED;}
 restore_sequence=((const volatile uint32_t *)(uintptr_t)restore_client)[5];
 if(restore_sequence==UINT32_MAX){state=4;return XW_PREPARE_BRIDGE_HANDLED;}
 state=5;return 0;
}
void xw_player_handoff_activation(uint32_t client,int native_result){
 if(state!=5||busy||pthread_self()!=owner||native_result)return;
 if(client!=restore_client||!restore_view(2,7)||
    ((const volatile uint32_t *)(uintptr_t)client)[5]<=restore_sequence){state=4;return;}
 state=6;
}
void xw_player_handoff_tick(void){
 if(state==6&&!busy&&pthread_self()==owner){
  busy=1;
  if(!restore_view(2,7)){state=4;busy=0;return;}
  int ready=xw_player_host_wireless_resume_handoff(epoch);
  if(!ready){
   if(xw_stock_prepare_view_unbind(&view))state=4;
   else {state=0;restore_client=restore_sequence=0;}
  }else if(ready!=XW_MODE_PENDING)state=4;
  busy=0;return;
 }
 if(state!=1||busy||pthread_self()!=owner)return;
 busy=1;
 if(xw_stock_prepare_view_check(&view,epoch)){state=4;busy=0;return;}
 int rc=xw_player_host_wireless_prepare_handoff(epoch);
 if(rc==XW_MODE_PENDING){busy=0;return;}
 if(rc){state=4;busy=0;return;}
 rc=xw_player_host_service_stop();
 if(rc==XW_PLAYER_BUSY){busy=0;return;}
 if(rc||xw_stock_prepare_view_check(&view,epoch)){state=4;busy=0;return;}
 state=2;
 uint32_t output=0;
 rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x112fcu)(0x613e60u,6,&output);
 state=rc?4:3;busy=0;
}
int xw_player_handoff_intercept(uint32_t root,uint32_t command,unsigned long original_owner){
 if(command!=6)return 0;
 if(state||busy||!original_owner||pthread_self()!=original_owner)return XW_PREPARE_BRIDGE_HANDLED;
 /* No radio authority and no SDK work means stock preparation owns the whole
  * transition. Do not consume it while waiting for wireless bootstrap. */
 if(!xw_player_host_wireless_has_authority()&&!xw_player_host_resources_idle())return 0;
 busy=1;
 if(xw_player_host_wireless_next_epoch(&epoch)){state=4;busy=0;return XW_PREPARE_BRIDGE_HANDLED;}
 owner=original_owner;
 if(xw_stock_prepare_view_bind(&view,root,command,epoch,owner)){state=4;busy=0;return XW_PREPARE_BRIDGE_HANDLED;}
 int sdk=xw_player_host_service_quiesce();
 if(sdk&&sdk!=XW_PLAYER_BUSY){state=4;busy=0;return XW_PREPARE_BRIDGE_HANDLED;}
 state=1;busy=0;
 /* Always return to the original action before invoking native preparation. */
 return XW_PREPARE_BRIDGE_HANDLED;
}
