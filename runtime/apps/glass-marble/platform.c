/* Exact existing JP1.11 stock/user-volume guard profile; no permissive fallback. */
#define EXCHANGE_GUARDS_ONLY
#define XNOW_LAB_NO_DETACH
#include "../../platform/espnow/exchange_lab.c"
#include "platform.h"
#include "full_profile.h"
int gm_storage_guard(void *p){return candidate_guard(p,XNOW_SESSION_CONFIGURE);}
static int rng(void *p,uint8_t out[4]){(void)p;int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;ssize_t n=read(fd,out,4);int r=close(fd);return n==4&&!r?0:-1;}
void gm_control_options(struct xnow_full_control_options *out,struct xnow_owner_gate *gate){
 struct xnow_full_control_options value={gate,&xnow_full_compiled_profile,candidate_guard,xnow_manager_stock_ipc_guard,xnow_owner_gate_radio_valid,rng,8,1,0};*out=value;
}
