/* Exercise production current-profile logic with original libraries on PC. */
#define main stock_session_unused_main
#include "../../runtime/platform/espnow/stock_wifi_session.c"
#undef main
#include <stdlib.h>
int xnow_manager_stock_ipc_guard(void *context,enum xnow_session_action action){
    (void)context;(void)action;return getenv("QQ_TEST_FIFO_ROOT")?0:-1;
}
/* Only delay timing is substituted; original FIFO request/reply IO still runs. */
int usleep(useconds_t microseconds){(void)microseconds;return 0;}
int main(void){
    int result=reconnect_current();
    if(result)return result;
    puts("XNOW_MANAGER_STOCK_TRANSPORT_PASS");return 0;
}
