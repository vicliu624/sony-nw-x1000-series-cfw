/* Pinned native page initializer. No persistence, radio or background work. */
#include <stdint.h>
extern uintptr_t xw_mode_ui_root(void);
extern uint32_t *xw_mode_param_get(uintptr_t,uint32_t *);
extern void xw_mode_param_set(uintptr_t,const uint32_t *);
extern uint32_t xw_mode_stock_init(void);
extern uint32_t xw_mode_request(uint32_t,uint32_t);
extern uint32_t xw_mode_post(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
extern uint32_t xw_mode_parent(void);
extern uint32_t xw_mode_index(void);
extern uint32_t xw_mode_category(uint32_t,uint32_t,uint32_t,uint32_t);
extern uint32_t xw_mode_selected;
static void three_choices(void){
 uintptr_t root=xw_mode_ui_root();
 if(!root||(root&3u))return;
 uintptr_t view=*(const uintptr_t *)(root+0x2b18u+0x1du*8u);
 if(!view||(view&3u))return;
 uint32_t parameters[15];xw_mode_param_get(view,parameters);
 if(parameters[13]==2){parameters[13]=3;xw_mode_param_set(view,parameters);}
}
uint32_t xw_wireless_native_init(void){
 three_choices();
 uint32_t reply=xw_mode_request(5,0);
 uint32_t row=reply&0xffffu;
 if((reply&0xffff0000u)!=0x574e0000u||row>2){
  uint32_t result=xw_mode_stock_init();
  three_choices();
  return result;
 }
 /* Match Sony's post/category order with the SDK row on the first post.
  * Running the binary initializer first would enqueue a competing row. */
 xw_mode_selected=row;
 (void)xw_mode_post(0x20106u,0,0x1du,row,0);
 uint32_t parent=xw_mode_parent();
 uint32_t index=xw_mode_index();
 uint32_t result=xw_mode_category(parent,0x9au,0,index);
 three_choices();
 return result;
}
