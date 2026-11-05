#ifndef XW_PLAYER_SERVICE_DRAIN_H
#define XW_PLAYER_SERVICE_DRAIN_H
#include "session_offer.h"
#include "player_broker.h"
enum {XW_DRAIN_READY=1,XW_DRAIN_SESSIONS,XW_DRAIN_BACKEND,XW_DRAIN_DONE,XW_DRAIN_FAULT};
struct xw_player_service_drain {struct xw_session_manager *manager;struct xw_player_broker *broker;struct xw_player *original;struct xw_player_session_offer **offers;unsigned count,phase;int error;};
/* Owner-thread only, fresh storage, offers array stable through completion.
 * Caller must register every owned session or drained will remain pending.
 * Does not install a native completion token or authorize original cleanup. */
int xw_player_service_drain_init(struct xw_player_service_drain *,struct xw_session_manager *,struct xw_player_broker *,struct xw_player_session_offer **,unsigned count);
int xw_player_service_drain_begin(struct xw_player_service_drain *,uint32_t reason);
/*0 only after sessions AND broker readers close; BUSY is incomplete. Fault
 * never counts as completion and is not auto-retried. Original stays borrowed. */
int xw_player_service_drain_step(struct xw_player_service_drain *);
#endif
