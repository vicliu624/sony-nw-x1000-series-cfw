#include "wireless_host.h"
#include "host_hook.h"
#include "host_managed_service.h"
#include "../wireless/native_boot.h"
extern int xw_native_rf_image_valid(void);
extern int xw_player_host_wireless_bind(struct xw_wireless_mode_policy *);
static struct xw_wireless_mode_policy authority;
static int attempted,result,image_checked;
int xw_player_host_wireless_initialization_status(void){
 return xw_player_host_wireless_has_authority()?0:attempted?result:XW_MODE_PENDING;
}
int xw_player_host_wireless_auto(void){
 /* An unbound/retiring player must not create a new authority during native
  * exit. Do not latch attempted: initial managed owner binding may still be
  * pending, in which case a later ordinary active tick can bootstrap. */
 if(xw_player_host_original_exiting())return XW_MODE_DENIED;
 if(xw_player_host_wireless_has_authority())return 0;
 if(attempted)return result;
 if(!image_checked){
  if(xw_native_rf_image_valid()!=1){attempted=1;return result=XW_MODE_DENIED;}image_checked=1;
 }
 struct xw_native_boot_observation observation;
 int rc=xw_native_rf_boot_observation(&observation);
 if(rc==XW_MODE_PENDING)return rc;
 attempted=1;if(rc)return result=rc;
 if(xw_native_rf_image_valid()!=1)return result=XW_MODE_DENIED;
 int mode;rc=xw_native_boot_mode(&observation,xw_native_boot_flag(),&mode);if(rc)return result=rc;
 rc=xw_mode_policy_init(&authority,observation.generation);if(rc)return result=rc;
 rc=xw_mode_policy_confirm_off(&authority,mode,1);if(rc)return result=rc;
 return result=xw_player_host_wireless_bind(&authority);
}
