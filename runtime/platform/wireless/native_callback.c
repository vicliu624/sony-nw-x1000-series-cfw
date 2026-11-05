/* Pinned Japanese1.11 callback candidate. Stock functions and the request
 * anchor are linker bindings, not writable function pointers or new syscalls.
 * An unpaired getpid anchor must never be mistaken for a successful request. */
#include <stdint.h>
#define REPLY_TAG 0x574d0000u
#define STAY 0x9a01u
#define KEEP_SELECTION 0x9a02u
extern uint32_t xw_native_mode_request(uint32_t operation,uint32_t row);
extern uint32_t xw_native_stock_confirm(uint32_t,uint32_t,uint32_t);
extern uint32_t xw_native_selected_row;
uint32_t xw_wireless_native_confirm(uint32_t first,uint32_t second,uint32_t event){
 if(event!=0xff0000u&&event!=0xff0001u)
  return xw_native_stock_confirm(first,second,event);
 uint32_t row=xw_native_selected_row;
 int back=event==0xff0001u;
 if(row>2)return back?0x5a01u:STAY;
 uint32_t reply=xw_native_mode_request(back?4u:2u,row);
 /* Back discards a preview when possible. A committed drain may continue
  * independently, and its status must not trap the user on this page. */
 if(back)return 0x5a01u;
 if((reply&0xffff0000u)!=REPLY_TAG)return STAY;
 /* A drain has already committed the requested row. Reinitializing now
  * would draw Sony's old binary preference while the SDK query is busy. */
 if(reply==(REPLY_TAG|1u))return KEEP_SELECTION;
 if((reply&0xffffu)!=0)return STAY;
 /* Sony's field remains binary. ESP-NOW disables ordinary Wi-Fi; only the
  * SDK stores the third mode. Preserve native queued-navigation behavior. */
 xw_native_selected_row=row==0?0u:1u;
 uint32_t result=xw_native_stock_confirm(first,second,event);
 xw_native_selected_row=row;
 /* The binary stock completion returns to its two-choice parent. Re-enter
  * this custom three-choice initializer instead, just as reopening the page
  * does, so its final queued selection comes from the committed SDK mode.
  * Keep asynchronous progress/error transitions exactly as returned. */
 if(result==0x5a01u)return 0x9a01u;
 return result;
}
