/* Private owner-loop bootstrap. Not a device installer or an SDK endpoint. */
#ifndef XW_PLAYER_HOST_HOOK_H
#define XW_PLAYER_HOST_HOOK_H
#include "provider.h"
/* The local service implementation supplies this strong symbol in the
 * same DSO. One bounded, nonblocking tick on the original GUI owner thread.
 * The default weak implementation is deliberately inert. */
void xw_player_host_dispatch(struct xw_player *);
/* Called only from the separately verified Met anchor. The service adapter
 * selects the proper owner using list/session identity, not first arrival.
 * Weak default is inert; this does not itself bind a queue provider. */
void xw_player_host_met_dispatch(uint32_t session,uint32_t cancel,uint32_t session_list);
/* Private loader diagnostics, not public SDK services. */
int xw_player_host_pid_resolved(void);
int xw_player_host_anchor_ready(void);
#endif
