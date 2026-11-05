/* Display-only analysis probe. No radio, player SDK, persistence or file I/O.
 * Fixed stock functions are supplied by the pinned analysis linker script. */
#include <stdint.h>
extern uintptr_t xw_probe_ui_root(void);
extern uint32_t *xw_probe_param_get(uintptr_t,uint32_t *);
extern void xw_probe_param_set(uintptr_t,const uint32_t *);
extern uint32_t xw_probe_stock_init(void);
extern uint32_t xw_probe_stock_confirm(uint32_t,uint32_t,uint32_t);
uint32_t xw_wireless_mode_probe_init(void){
 uintptr_t root=xw_probe_ui_root();
 if(root&&!(root&3u)){
  uintptr_t view=*(const uintptr_t *)(root+0x2b18u+0x1du*8u);
  if(view&&!(view&3u)){
   uint32_t parameters[15];xw_probe_param_get(view,parameters);
   if(parameters[13]==2||parameters[13]==3){
    parameters[13]=3;xw_probe_param_set(view,parameters);
   }
  }
 }
 return xw_probe_stock_init();
}
uint32_t xw_wireless_mode_probe_confirm(uint32_t a,uint32_t b,uint32_t event){
 if(event==0xff0000u||event==0xff0001u)return 0x5a01u;
 return xw_probe_stock_confirm(a,b,event);
}
