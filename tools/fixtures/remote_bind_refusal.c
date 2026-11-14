/* Offline-only fault injection at the exact service startup boundary. */
#include "../../runtime/platform/player/managed_client.h"
#include <stdio.h>
#ifdef WR_TEST_HANDOFF_REFUSAL
#include "../../runtime/platform/espnow/xnow_handoff.h"
int __wrap_xnow_handoff_adopt_reader(struct xnow_handoff *h,int fd,const uint8_t cookie[16]){
 (void)h;(void)fd;(void)cookie;puts("REMOTE_HANDOFF_REFUSAL_FIXTURE");fflush(stdout);return -1;
}
#endif
int __wrap_xw_managed_client_bind_stock(struct xw_player *p,struct xw_managed_client *c,
 int fd,uint64_t generation,unsigned timeout,volatile int *stop){
 (void)p;(void)c;(void)fd;(void)generation;(void)timeout;(void)stop;
 puts("REMOTE_BIND_REFUSAL_FIXTURE");fflush(stdout);return XW_PLAYER_UNAVAILABLE;
}
