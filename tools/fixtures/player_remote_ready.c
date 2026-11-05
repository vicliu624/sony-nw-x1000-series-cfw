#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "stock_info_host.c"
#include "../../runtime/store/stock_fs_bridge.h"
#include <sys/stat.h>
unsigned test_mode=2,test_image=1,test_same_device,test_bad_directory,test_stat_failure,test_transition,test_stat_calls;
int xw_player_host_wireless_remote_mode(void){return (int)test_mode;}
int xw_native_rf_image_valid(void){return (int)test_image;}
int hb_target_lstat(const char *path,struct hb_target_stat *out){
 test_stat_calls++;if(test_stat_failure)return -1;memset(out,0,sizeof *out);
 int contents=path[1]=='c';out->st_dev=contents&&!test_same_device?2:1;
 out->st_mode=contents&&test_bad_directory?S_IFLNK:S_IFDIR;
 if(contents&&test_transition)*(volatile uint32_t *)(uintptr_t)(0x613e60u+(test_transition==1?4u:8u))=8;
 return 0;
}
