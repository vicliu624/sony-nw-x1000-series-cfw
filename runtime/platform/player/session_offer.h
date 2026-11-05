#ifndef XW_PLAYER_SESSION_OFFER_H
#define XW_PLAYER_SESSION_OFFER_H
#include "managed_channel.h"
/* Internal broker workspace for ONE approved launch, fresh static/heap storage.
 * Trusted caller supplies grants and a private datagram delivery channel.
 * No app identity lookup, user consent or original manager hooks are implied. */
struct xw_player_session_offer {struct xw_managed_player player;struct xw_managed_channel channel;};
int xw_player_session_offer(struct xw_player_session_offer *,struct xw_session_manager *,struct xw_player *backend,int delivery,uint32_t requested,uint32_t authorized,uint64_t now);
/* Pump original owner only. Initial HELLO has3000ms to arrive; no commands
 * before it. Native observation sampling/refresh remains caller responsibility. */
int xw_player_session_offer_tick(struct xw_player_session_offer *,uint64_t now);
#endif
