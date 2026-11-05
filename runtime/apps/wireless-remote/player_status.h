#ifndef WALKMAN_REMOTE_PLAYER_STATUS_H
#define WALKMAN_REMOTE_PLAYER_STATUS_H
#include "link.h"
#include "../../platform/player/player.h"
/* Does not query/control the player or start RF. Output commits only on success.
 * Unsupported snapshot fields are cleared rather than sent as stale metadata. */
int wr_player_status(struct wr_status *,const struct xw_player_snapshot *,
                     uint64_t session,uint32_t sequence,uint32_t commands);
#endif
