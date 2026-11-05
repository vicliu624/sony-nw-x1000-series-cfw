#ifndef XW_MANAGED_HOST_H
#define XW_MANAGED_HOST_H
#include "deferred_prepare.h"
enum {XW_HOST_ACTIVE=1,XW_HOST_STOPPING,XW_HOST_STOPPED,XW_HOST_FAULT};
struct xw_managed_host {
 struct xw_session_manager manager;
 struct xw_player_service_drain drain;
 struct xw_deferred_prepare prepare;
 struct xw_player_session_offer *offers[XW_SESSION_SLOTS];
 unsigned slots[XW_SESSION_SLOTS],count,phase,busy;
 unsigned long owner;
 int last_client_error;
 uint64_t refresh_at[XW_SESSION_SLOTS];
 unsigned refreshed[XW_SESSION_SLOTS];
 void *stop_context;
 int (*stop_poll)(void *,uint64_t);
};
/* Internal trusted host, not a listener or app authorization policy. Fresh host
 * and offer storage; caller supplies a new generation and authorized grants.
 * Host owns SDK session/channel cleanup and broker closure, borrowing its
 * original backend. Storage must outlive all operations; no stack workspaces.
 */
int xw_managed_host_init(struct xw_managed_host *,struct xw_player_broker *,
 uint64_t generation,uint32_t supported,struct xw_player_session_offer **,unsigned count);
int xw_managed_host_offer(struct xw_managed_host *,int delivery,uint32_t requested,uint32_t authorized,uint64_t now);
/* Caller ticks the broker separately on its qualified original owner. Tick
 * automatically samples READ-authorized adopted sessions at most every 200 ms
 * per session; first sample and clock rollback refresh immediately. Explicit
 * reads and bounded channel/command/close pumping remain on every tick.
 * One failed client is released independently; inspect last_client_error.
 */
int xw_managed_host_tick(struct xw_managed_host *,uint64_t now);
int xw_managed_host_stop(struct xw_managed_host *,uint32_t reason);
/* Optional owner-supplied ordinary-stop retirement. Poll receives the SDK
 * generation after the broker drain; BUSY retains STOPPING, errors latch FAULT.
 * It must also cover any registered native-exit dependency before user rearm.
 * No hardware implementation or timeout-based completion is supplied here. */
int xw_managed_host_stop_dependency(struct xw_managed_host *,void *,int (*)(void *,uint64_t));
/* Candidate native-exit continuation. Trusted caller must qualify context,
 * epoch, event ordering and original manager deadlines before selecting it.
 * The same tick path drains and forwards once; no native hook is installed. */
int xw_managed_host_prepare(struct xw_managed_host *,uint32_t reason,uint64_t epoch,
 void *context,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t));
#endif
