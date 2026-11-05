/* Original-control prototype: no raw display/input, persistence or RF access.
 * A separate qualified owner bridge must implement the request operations.
 * Opening/query/preview/cancel must never enqueue a start/stop operation. */
#include "native_page.h"
extern uint32_t wr_remote_page_request(uint32_t,uint32_t);
extern uint32_t wr_page_post(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
extern uint32_t wr_page_parent(void);
extern uint32_t wr_page_index(void);
extern void wr_page_set_category(uint32_t,uint32_t,uint32_t,uint32_t);
extern uint32_t wr_page_set_state(uint32_t,uint32_t,uint32_t);
extern void wr_page_stock_home(void);
extern void wr_page_stock_playback(uint32_t *,uint32_t *);
static int row_reply(uint32_t value){
 return (value&0xffff0000u)==WR_NATIVE_PAGE_ROW_TAG&&(value&0xffffu)<=1;
}
static void show_settings(void){
 (void)wr_page_post(0x20106u,0,0x61u,11,0);
 wr_page_set_category(0,2,0,11);
}
uint32_t wr_remote_page_open(void){
 uint32_t result=wr_remote_page_request(WR_NATIVE_PAGE_OPEN,0);
 return row_reply(result)?(WR_NATIVE_PAGE_GROUP<<8)|1u:0x0202u;
}
uint32_t wr_remote_page_init(uint32_t first,uint32_t second,uint32_t third){
 (void)second;(void)third;
 uint32_t value=wr_remote_page_request(WR_NATIVE_PAGE_QUERY,0);
 if(!row_reply(value)){
  /* The dispatcher ignores initializer return values. Leave the Remote
   * waiting state explicitly so the Settings ready event can complete. */
  (void)wr_remote_page_request(WR_NATIVE_PAGE_CANCEL,0);
  show_settings();
  (void)wr_page_set_state(first,2,1);
  return 0;
 }
 (void)wr_page_post(0x20106u,0,WR_NATIVE_PAGE_CONTROL,value&0xffffu,0);
 uint32_t parent=wr_page_parent(),index=wr_page_index();
 wr_page_set_category(parent,WR_NATIVE_PAGE_GROUP,0,index);
 return 0;
}
uint32_t wr_remote_page_select(uint32_t first,uint32_t second,uint32_t row){
 (void)first;(void)second;
 if(row<=1)(void)wr_remote_page_request(WR_NATIVE_PAGE_PREVIEW,row);
 return 0;
}
uint32_t wr_remote_page_back(uint32_t first,uint32_t second,uint32_t third){
 (void)first;(void)second;(void)third;
 uint32_t cancelled=wr_remote_page_request(WR_NATIVE_PAGE_CANCEL,0);
 if(cancelled!=WR_NATIVE_PAGE_STATUS_TAG)return (WR_NATIVE_PAGE_GROUP<<8)|2u;
 /* This page is entered from Japanese Settings row11. Queue that actual
  * control before entering its waiting-for-ready substate. Stock73608 is a
  * playback shortcut, not a parent-stack pop; do not call it here. */
 show_settings();
 return 0x0201u;
}
uint32_t wr_remote_page_confirm(uint32_t first,uint32_t second,uint32_t event){
 if(event==0xff0001u)return wr_remote_page_back(first,second,event);
 if(event!=0xff0000u)return 0;
 uint32_t result=wr_remote_page_request(WR_NATIVE_PAGE_APPLY,0);
 if((result&0xffff0000u)!=WR_NATIVE_PAGE_STATUS_TAG||(result&0xffffu)>1)
  return (WR_NATIVE_PAGE_GROUP<<8)|2u;
 return wr_remote_page_back(first,second,event);
}
uint32_t wr_remote_page_home(uint32_t first,uint32_t second,uint32_t third){
 (void)first;(void)second;(void)third;
 (void)wr_remote_page_request(WR_NATIVE_PAGE_CANCEL,0);
 wr_page_stock_home();return 0x3301u;
}
uint32_t wr_remote_page_playback(uint32_t first,uint32_t second,uint32_t third){
 (void)first;(void)second;(void)third;
 (void)wr_remote_page_request(WR_NATIVE_PAGE_CANCEL,0);
 uint32_t group=0,substate=2;
 wr_page_stock_playback(&group,&substate);
 return ((group&255u)<<8)|(substate&255u);
}
