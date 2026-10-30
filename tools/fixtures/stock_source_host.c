#include "stock_info_host.c"
unsigned xw_test_source_ready=1;
int xw_stock_media_source_ready(void){return xw_test_source_ready!=0;}
