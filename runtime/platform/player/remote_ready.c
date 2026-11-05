#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "remote_ready.h"
#include "wireless_host.h"
#include <stdint.h>
#include <sys/stat.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
extern int xw_native_rf_image_valid(void);
static int sample(uint32_t out[3],int verify){
 if(verify){
  uintptr_t client=((uintptr_t (*)(void))(uintptr_t)0x265510u)();
  uintptr_t environment=((uintptr_t (*)(void))(uintptr_t)0xe5f4u)();
  if(client!=0x820f68u||environment!=0x613e2cu)return 0;
 }
 const volatile uint32_t *root=(const volatile uint32_t *)(uintptr_t)0x613e60u;
 uint32_t command=root[1];
 /* Command1 is the verified sleep-prepare route. Command11 leads to the
  * separate manager request19 path; neither is an active remote admission. */
 if(command>21||command==1||command==3||command==6||command==8||command==11||root[0x2c/4]!=0x66efe8u||
    *(const volatile uint32_t *)(uintptr_t)0x66efe8u||
    ((const volatile uint32_t *)(uintptr_t)0x820f68u)[1]!=2||((const volatile uint32_t *)(uintptr_t)0x613e2cu)[1])return 0;
 out[0]=command;out[1]=root[2];out[2]=root[0x4c/4];return 1;
}
int xw_player_remote_software_ready(void){
 if(xw_player_host_wireless_remote_mode()!=XW_WIRELESS_MODE_ESPNOW||xw_native_rf_image_valid()!=1)return 0;
 uint32_t before[3],after[3];if(!sample(before,1))return 0;
 struct stat root,volume;
 if(lstat("/",&root)||lstat("/contents",&volume)||!S_ISDIR(root.st_mode)||!S_ISDIR(volume.st_mode)||root.st_dev==volume.st_dev)return 0;
 if(!sample(after,0))return 0;
 for(unsigned i=0;i<3;i++)if(before[i]!=after[i])return 0;
 return 1;
}
int xw_player_remote_state_active(void){uint32_t state[3];return sample(state,0);}
