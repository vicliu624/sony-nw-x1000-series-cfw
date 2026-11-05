#include "stock_host_image.c"
#include "../../runtime/platform/player/stock_prepare_view.h"
struct xw_stock_prepare_view view;
int test_bind(uint32_t root,uint32_t command){return xw_stock_prepare_view_bind(&view,root,command,0x1122334455667788ull,17);}
int test_bind_zero(void){return xw_stock_prepare_view_bind(&view,0x613e60,3,0,17);}
int test_check(void){return xw_stock_prepare_view_check(&view,0x1122334455667788ull);}
int test_stale(void){return xw_stock_prepare_view_check(&view,0x1122334455667789ull);}
int test_unbind(void){return xw_stock_prepare_view_unbind(&view);}
