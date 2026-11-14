#include "mode_policy.h"
#include <stdint.h>
extern int xw_native_rf_image_valid(void);
static int queue_native(uint32_t event){
 if(xw_native_rf_image_valid()!=1)return XW_MODE_FAULT;
 /* Original global event queue, with its native duplicate-coalescing flag.
  * No message pointer or private worker queue handle is retained. */
 uint32_t queued=((uint32_t (*)(uint32_t,uint32_t,uint32_t,uint32_t,unsigned short))0xa57f0u)(event,0,0,0,1);
 return queued==1?0:queued==0?XW_MODE_PENDING:XW_MODE_FAULT;
}
int xw_native_rf_stop_request(void){return queue_native(0x4c0006u);}
/* Same stock request emitted by wireless lifecycle command 10/13/18. */
int xw_native_rf_reconnect_request(void){return queue_native(0x4c0005u);}
