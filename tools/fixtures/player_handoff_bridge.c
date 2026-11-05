#include "stock_info_host.c"
#include "../../runtime/platform/player/host_handoff_bridge.h"
unsigned test_radio_wait,test_sdk_wait,test_radio_calls,test_sdk_calls;
int xw_player_host_wireless_has_authority(void){return 1;}
int xw_player_host_resources_idle(void){return 0;}
unsigned test_resume_wait,test_resume_calls;
int test_resume_result;
int xw_player_host_wireless_next_epoch(uint64_t *epoch){static uint64_t serial;*epoch=++serial;return 0;}
int test_radio_result,test_sdk_result;
int xw_player_host_wireless_prepare_handoff(uint64_t epoch){
 if(!epoch)return -1;test_radio_calls++;
 if(test_radio_wait){test_radio_wait--;return 1;}return test_radio_result;
}
int xw_player_host_service_stop(void){
 test_sdk_calls++;if(test_sdk_wait){test_sdk_wait--;return -4;}return test_sdk_result;
}
int test_start(void){return xw_player_handoff_intercept(0x613e60,6,17);}
int test_other(void){return xw_player_handoff_intercept(0x613e60,3,17);}
int xw_player_host_service_quiesce(void){return 0;}
int xw_player_host_wireless_resume_handoff(uint64_t epoch){
 if(!epoch)return -1;test_resume_calls++;if(test_resume_wait){test_resume_wait--;return 1;}return test_resume_result;
}
int test_resume_begin(void){return xw_player_handoff_resume_begin(0x613e60,17);}
void test_activation(uint32_t client,int result){xw_player_handoff_activation(client,result);}
