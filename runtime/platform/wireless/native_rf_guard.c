#include <stdint.h>
extern int xw_stock_image_match(uint32_t,uint32_t,const unsigned char[32]);
struct rf_guard {uint32_t address,bytes;unsigned char digest[32];};
static const struct rf_guard guards[]=XW_NATIVE_RF_GUARDS;
int xw_native_rf_image_valid(void){
 for(unsigned i=0;i<sizeof guards/sizeof *guards;i++)
  if(xw_stock_image_match(guards[i].address,guards[i].bytes,guards[i].digest))return 0;
 return 1;
}
