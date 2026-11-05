/* Lifecycle boundary fixture; no driver, RF observation or GUI executes. */
#include <assert.h>
#include <stdio.h>
#include "../../runtime/platform/player/wireless_host.h"
#include "../../runtime/platform/wireless/native_boot.h"
static unsigned exiting=1,authority,observations,binds;
int xw_player_host_original_exiting(void){return exiting;}
int xw_native_rf_image_valid(void){return 1;}
int xw_player_host_wireless_has_authority(void){return authority;}
int xw_native_rf_boot_observation(struct xw_native_boot_observation *o){
 observations++;o->generation=19;o->before=o->after=2;o->modules_clear=o->entropy_valid=1;return 0;
}
int xw_native_boot_flag(void){return 1;}
int xw_native_boot_mode(const struct xw_native_boot_observation *o,int flag,int *mode){
 assert(o->generation==19&&flag==1);*mode=XW_WIRELESS_MODE_OFF;return 0;
}
int xw_player_host_wireless_bind(struct xw_wireless_mode_policy *p){
 struct xw_wireless_mode_snapshot state;assert(!xw_mode_policy_snapshot(p,&state));
 assert(state.selected==XW_WIRELESS_MODE_OFF&&state.off_verified&&!state.active);
 binds++;authority=1;return 0;
}
int main(void){
 int first=xw_player_host_wireless_auto();
 puts(observations?"EXIT_AUTO_BOOT_OBSERVED":"EXIT_AUTO_NO_BOOT");fflush(stdout);
 assert(first==XW_MODE_DENIED);
 assert(!observations&&!binds&&!authority);
 assert(xw_player_host_wireless_initialization_status()==XW_MODE_PENDING);
 exiting=0;assert(!xw_player_host_wireless_auto());assert(observations==1&&binds==1&&authority);
 exiting=1;assert(xw_player_host_wireless_auto()==XW_MODE_DENIED);assert(observations==1&&binds==1);
 puts("WIRELESS_AUTO_EXIT_GUARD_PASS");fflush(stdout);return 0;
}
