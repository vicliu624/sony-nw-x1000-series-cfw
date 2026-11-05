#include "stock_info_host.c"
#include "../../runtime/platform/player/sleep_native.h"
unsigned test_radio_wait=1,test_quiesced,test_sdk_stopped;
unsigned test_resume_calls,test_resume_wait;
int xw_player_host_original_exiting(void){return 0;}
int xw_player_host_service_quiesce(void){test_quiesced++;return 0;}
int xw_player_host_service_stop(void){test_sdk_stopped++;return 0;}
int xw_player_host_wireless_prepare_handoff(uint64_t epoch){if(!epoch)return -1;if(test_radio_wait){test_radio_wait--;return 1;}return 0;}
int xw_player_host_wireless_next_epoch(uint64_t *epoch){static uint64_t serial;*epoch=++serial;return 0;}
int xw_player_host_wireless_resume_handoff(uint64_t epoch){if(!epoch)return -1;test_resume_calls++;if(test_resume_wait){test_resume_wait--;return 1;}return 0;}
