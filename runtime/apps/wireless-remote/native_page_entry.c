#include "native_page.h"
extern uint32_t wr_page_row_id(uint32_t);
extern uint32_t wr_page_stock_settings_select(uint32_t,uint32_t,uint32_t);
extern uint32_t wr_page_stock_wireless_select(uint32_t,uint32_t,uint32_t);
extern uint32_t wr_remote_page_request(uint32_t,uint32_t);
uint32_t wr_remote_page_entry(uint32_t first,uint32_t second,uint32_t index){
 if(wr_page_row_id(index)!=0xfd0000u)
  return wr_page_stock_settings_select(first,second,index);
 return wr_remote_page_open();
}
uint32_t wr_remote_page_wireless_entry(uint32_t first,uint32_t event,uint32_t index){
 /* Only Wireless Mode reuses control29. Refuse before Sony changes menu
  * state or queues any drawing when Remote still owns the control. */
 if(wr_page_row_id(index)==0xf60005u&&
    wr_remote_page_request(WR_NATIVE_PAGE_ALLOW_WIRELESS,0)!=WR_NATIVE_PAGE_STATUS_TAG)
  return 0x5a02u;
 return wr_page_stock_wireless_select(first,event,index);
}
