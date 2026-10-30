/* Exact JP1.11/user-volume guard profile from the accepted native lab. */
#define EXCHANGE_GUARDS_ONLY
#define XNOW_LAB_NO_DETACH
#include "../../platform/espnow/exchange_lab.c"
#include "chat_owner_platform.h"
void chat_owner_options(struct xnow_control_options *options){
    struct xnow_control_options value={0,candidate_guard,xnow_manager_stock_ipc_guard,8,1};
    *options=value;
}
uint32_t chat_owner_now_ms(void){return milliseconds();}
