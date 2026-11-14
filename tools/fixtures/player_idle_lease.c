#include "stock_host_image.c"
#include "../../runtime/platform/player/stock_idle_lease.h"
static struct xw_stock_idle_lease lease;
void *memset(void *p,int value,unsigned bytes){unsigned char *b=p;while(bytes--)*b++=(unsigned char)value;return p;}
int test_idle_step(int active){return xw_stock_idle_lease_step(&lease,active);}
int test_idle_burst(int active){return xw_stock_idle_lease_limit(&lease,active,20000u);}
unsigned test_idle_held(void){return lease.held;}
void test_idle_reset(void){struct xw_stock_idle_lease empty={0};lease=empty;}
