#ifndef XW_PLAYER_MANAGED_RPC_H
#define XW_PLAYER_MANAGED_RPC_H
#include "managed.h"
#include "rpc_wire.h"
/* One pre-authorized adapter per channel. No self-reported session/grants in
 * the frame. Serial IDs must increase and never wrap during that session.
 * No listener/authentication is installed. Caller supplies large response
 * scratch in static/heap storage and executes only on the backend owner. */
int xw_managed_rpc_execute(struct xw_managed_player *,const unsigned char *,size_t,struct xw_rpc_response *);
#endif
