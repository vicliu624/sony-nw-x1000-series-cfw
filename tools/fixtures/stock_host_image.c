/* Separate-address ARM harness; loader identity is modeled, stock AudioC is not. */
#include "../../runtime/platform/player/stock_volume.h"
#include <stdint.h>
struct image_info {const char *name;void *base;const char *symbol;void *address;};
unsigned xw_test_loaded=1;unsigned long xw_test_thread=17;
int dladdr(const void *address,struct image_info *out){if(!xw_test_loaded)return 0;uintptr_t a=(uintptr_t)address;if(a<0x8000||a>0x4de000)return 0;out->name="/usr/local/bin/SpiderApp";out->base=(void *)0x8000;out->symbol=0;out->address=0;return 1;}
unsigned long pthread_self(void){return xw_test_thread;}
void _start(void){}
