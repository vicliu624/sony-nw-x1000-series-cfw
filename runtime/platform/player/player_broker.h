#ifndef XW_PLAYER_BROKER_H
#define XW_PLAYER_BROKER_H
#include "provider.h"
#include "metadata_async.h"
/* Optional internal queue provider. No callback is installed by default. close
 * must quiesce its Met callback before freeing exchange/reader state; BUSY keeps
 * the broker and original player alive for a later close attempt. */
struct xw_player_queue_provider {
 void *context;
 int (*browse)(void *,const struct xw_media_query *,uint64_t now,struct xw_media_item *,struct xw_media_page *);
 int (*revoke)(void *,uint64_t now);
 int (*close)(void *);
};
struct xw_player_broker {
    struct xw_player player;
    struct xw_player *backend;
    struct xw_metadata_async metadata;
    struct xw_children_async library;
    struct xw_stock_children_page browse_scratch;
    unsigned metadata_ready,library_ready;
    struct xw_player_queue_provider queue;
    unsigned long owner;
    unsigned queue_revoke_pending;
};
int xw_player_broker_bind(struct xw_player_broker *,struct xw_player *backend);
int xw_player_broker_attach_queue(struct xw_player_broker *,const struct xw_player_queue_provider *);
/* Owner tick revokes cached/pending metadata when the original source is off.
 * No storage read occurs here; all native projections run in the reader. */
void xw_player_broker_tick(struct xw_player_broker *,unsigned long long now_ms);
#endif
