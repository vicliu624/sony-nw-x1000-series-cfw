/* Private pinned callback receiver. Linked into the optional host profile only.
 * Missing image qualification or worker provisioning returns native error1. */
#include "native_rf_dispatch.h"
extern int *__errno_location(void);
__attribute__((weak)) int xw_native_rf_image_valid(void){return 0;}
__attribute__((weak)) int xw_native_rf_permission(void){return -1;}
__attribute__((weak)) int xw_native_rf_bootstrap_gui(void){return -1;}
__attribute__((weak)) int xw_native_rf_bootstrap_worker(void){return -1;}
__attribute__((weak)) int xw_native_rf_gui_owner(void){return 0;}
__attribute__((weak)) int xw_native_rf_poweroff_note(int result){(void)result;return -1;}
__attribute__((weak)) int xw_native_rf_cleanup_permission(void){return -1;}
__attribute__((weak)) int xw_native_rf_disable_checkpoint(uint32_t event){(void)event;return -1;}
int xw_native_rf_caller(uintptr_t caller){
 for(unsigned i=0;i<8;i++)if(caller==0x4d8718u+i*28u)return 1;
 for(unsigned i=0;i<4;i++)if(caller==0x4d884cu+i*28u)return 1;
 return 0;
}
int xw_native_rf_dispatch(uint32_t operation,uint32_t a,uint32_t b,uint32_t c,uintptr_t caller){
 static const uintptr_t target[]={0xda9c,0xe108,0xda3c,0xe2ac,0xe030,0xd640,0xd880,0xdf4c};
 int saved=*__errno_location(),result=1;
 if(operation>=1&&operation<=8&&caller==0x4d8700u+(operation-1)*28u+24u&&
    xw_native_rf_image_valid()==1&&xw_native_rf_permission()==0){
  *__errno_location()=saved;
  result=((int (*)(uint32_t,uint32_t,uint32_t))target[operation-1])(a,b,c);
  saved=*__errno_location();
 }
 else if(operation>=13&&operation<=16&&caller==0x4d884cu+(operation-13)*28u&&xw_native_rf_image_valid()==1){
  static const uintptr_t cleanup[]={0xd4fc,0xd958,0xd8bc,0xddfc};
  int permission=xw_native_rf_cleanup_permission();
  if(permission==2){(void)xw_native_rf_poweroff_note(0);result=0;}
  else if(!permission){
   *__errno_location()=saved;result=((int (*)(void))cleanup[operation-13])();saved=*__errno_location();
   if(operation==13)(void)xw_native_rf_poweroff_note(result);
  }
 }
 *__errno_location()=saved;return result;
}
