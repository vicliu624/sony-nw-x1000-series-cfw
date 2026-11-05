#include "../../runtime/platform/player/stock_pending.h"
struct xw_stock_pending pending;
unsigned long test_thread=7;
unsigned long pthread_self(void){return test_thread;}
struct image_info {const char *name;void *base;const char *symbol;void *address;};
int dladdr(const void *address,struct image_info *out){(void)address;out->name="SpiderApp";out->base=(void *)0x8000;out->symbol=0;out->address=0;return 1;}
void _start(void){for(;;){}}
