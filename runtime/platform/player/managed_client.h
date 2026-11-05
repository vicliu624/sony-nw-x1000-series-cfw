#ifndef XW_MANAGED_PLAYER_CLIENT_H
#define XW_MANAGED_PLAYER_CLIENT_H
#include "managed_remote.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Private development API. Fresh zeroed static/heap objects; serialized worker
 * use only. Manager supplies descriptor, generation and authority externally.
 * No auto-start, reconnect or rebind after a failed attempt. */
struct xw_managed_client {struct xw_managed_remote remote;struct xw_rpc_response response;uint64_t generation,correlation;uint32_t serial;unsigned used;};
int xw_managed_client_bind(struct xw_player *,struct xw_managed_client *,int fd,uint64_t generation,unsigned timeout_ms,volatile int *,void *clock_context,int (*clock)(void *,uint64_t *));
/* Normal stock-libc clock path; callback variant remains for explicit tests. */
int xw_managed_client_bind_stock(struct xw_player *,struct xw_managed_client *,int fd,uint64_t generation,unsigned timeout_ms,volatile int *);
int xw_managed_client_status(struct xw_managed_client *,struct xw_session_snapshot *);
/* Requires a matching host with PLAY_MODE support; old hosts do not advertise
 * this extension. Do not probe it automatically on unqualified legacy hosts. */
int xw_managed_client_play_mode(struct xw_managed_client *,uint32_t *native,uint32_t *menu_index);
int xw_managed_client_sync(struct xw_managed_client *,struct xw_player_snapshot *,uint64_t *sequence);
int xw_managed_client_events(struct xw_managed_client *,uint64_t after,uint32_t limit,struct xw_service_event *,uint32_t capacity,uint32_t *count,uint64_t *next);
/* Confirms session close, does not destroy the local player context. Follow
 * with xw_player_close for local detach. A transport failure is not a receipt. */
int xw_managed_client_end(struct xw_managed_client *,struct xw_session_snapshot *receipt);
#ifdef __cplusplus
}
#endif
#endif
