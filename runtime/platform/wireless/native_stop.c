#include "mode_policy.h"
#include <stdint.h>
extern int xw_native_rf_image_valid(void);
int xw_native_rf_stop_request(void){
 if(xw_native_rf_image_valid()!=1)return XW_MODE_FAULT;
 /* Original global event queue, with its native duplicate-coalescing flag.
  * No message pointer or private worker queue handle is retained. */
 uint32_t queued=((uint32_t (*)(uint32_t,uint32_t,uint32_t,uint32_t,unsigned short))0xa57f0u)(0x4c0006u,0,0,0,1);
 return queued==1?0:queued==0?XW_MODE_PENDING:XW_MODE_FAULT;
}
