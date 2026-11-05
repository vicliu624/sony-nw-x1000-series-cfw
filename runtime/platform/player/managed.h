/* Private synchronous owner-thread adapter; not an installed IPC service. */
#ifndef XW_PLAYER_MANAGED_H
#define XW_PLAYER_MANAGED_H
#include "provider.h"
#include "../services/request.h"
#include "../services/events.h"
struct xw_managed_player {struct xw_session_manager *manager;struct xw_player *backend;struct xw_request_ledger requests;struct xw_player observer;struct xw_service_events events;unsigned busy,unavailable,notification_fault;void *mode_context;int (*mode_read)(void *,uint32_t *,uint32_t *);};
/* Trusted host registration, not client-supplied code. Read requires an active
 * READ grant; outputs commit only after post-call epoch validation. */
int xw_managed_player_mode_bind(struct xw_managed_player *,void *,int (*)(void *,uint32_t *,uint32_t *));
int xw_managed_player_mode_get(struct xw_managed_player *,uint32_t *,uint32_t *);
int xw_managed_player_bind(struct xw_managed_player *,struct xw_session_manager *,struct xw_session_handle,struct xw_player *);
int xw_managed_player_snapshot(struct xw_managed_player *,struct xw_player_snapshot *);
/* Per-session observation history; no backend/global poll cursor is consumed. */
int xw_managed_player_poll(struct xw_managed_player *,struct xw_player_snapshot *,uint32_t *changes);
/* Owner calls periodically, even with no IPC consumer. No lossless claim
 * between samples. snapshot_sync obtains fresh snapshot + sequence together. */
int xw_managed_player_refresh(struct xw_managed_player *);
int xw_managed_player_snapshot_sync(struct xw_managed_player *,struct xw_player_snapshot *,uint64_t *sequence);
/* Returns XW_EVENTS_*; denied/closed session requires resync/reconnect.
 * Caller already holds this exact authorized adapter; no credentials here. */
int xw_managed_player_events(struct xw_managed_player *,uint64_t generation,uint64_t after,struct xw_service_event *,uint32_t capacity,uint32_t *count,uint64_t *next);
int xw_managed_player_browse(struct xw_managed_player *,const struct xw_media_query *,struct xw_media_item *,uint32_t,struct xw_media_page *);
/* Request IDs strictly increase per session; duplicates return retained result,
 * including BUSY. PLAY_ITEM is delegated only when the backend advertises it;
 * IDs/container/revision are retained canonically. A new explicit command ID
 * may poll a backend's documented pre-admission preparation; this adapter never
 * retries or advances a command automatically, including after ACCEPTED or
 * UNCERTAIN. Acceptance is not observed playback completion. */
int xw_managed_player_command(struct xw_managed_player *,uint64_t request,const struct xw_player_command *);
int xw_managed_player_close(struct xw_managed_player *);
#endif
