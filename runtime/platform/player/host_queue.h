/* Process-lifetime preload queue adapter, internal to the analysis host. */
#ifndef XW_HOST_QUEUE_H
#define XW_HOST_QUEUE_H
#include "player_broker.h"
/* GUI owner only, after broker bind. Requires an observed qualified Met anchor. */
int xw_player_host_queue_attach(struct xw_player_broker *);
#endif
