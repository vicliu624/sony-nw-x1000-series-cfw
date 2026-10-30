#ifndef XNOW_OWNER_GATE_H
#define XNOW_OWNER_GATE_H
#include "xnow_full_control.h"
/* Experimental SDK platform component; device ownership is not qualified.
 * Abstract socket coordinates custom owners (same namespace as legacy chat),
 * not Sony/USB/kernel ownership. Pipe HUP/stop revokes data writes but retains
 * radio exclusion so original restoration can finish. The storage callback
 * must independently prove real user-volume/USB access; mount alone is not it.
 * All methods except the external stop token run in the serialized owner loop. */
struct xnow_owner_gate {
 int socket_fd,command_fd,pid,stopping,data_revoked,radio_fault;
 uint64_t socket_device,socket_inode,command_device,command_inode;
 const volatile int *stop_token;
 void *storage_context;int (*storage_guard)(void *);
};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_owner_gate_open(struct xnow_owner_gate *,int inherited_command_pipe,const volatile int *stop_token,void *,int (*storage_guard)(void *));
int xnow_owner_gate_radio_valid(void *);
int xnow_owner_gate_stop_requested(struct xnow_owner_gate *);
int xnow_owner_gate_storage_guard(void *);
/* Owner loop calls this before accepting IPC work: handles pipe/stop request,
 * then advances the real full controller without prematurely dropping lease. */
int xnow_owner_gate_step(struct xnow_owner_gate *,struct xnow_full_control *);
/* Refuses release until the original-action controller proves finished. */
int xnow_owner_gate_release(struct xnow_owner_gate *,const struct xnow_full_control *);
#ifdef __cplusplus
}
#endif
#endif
