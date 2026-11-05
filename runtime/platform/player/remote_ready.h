#ifndef XW_PLAYER_REMOTE_READY_H
#define XW_PLAYER_REMOTE_READY_H
/* Software admission only. Cached busy0 is not physical USB-disconnect proof.
 * Called only by the qualified original Settings owner during launch. */
int xw_player_remote_software_ready(void);
/* Fast owner-loop read after successful image qualification; no I/O/RPC. */
int xw_player_remote_state_active(void);
#endif
