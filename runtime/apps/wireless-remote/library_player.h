#ifndef WALKMAN_REMOTE_LIBRARY_PLAYER_H
#define WALKMAN_REMOTE_LIBRARY_PLAYER_H
#include "library_wire.h"
struct wr_library_ledger {struct wr_library_request last;struct wr_library_reply reply;unsigned have,busy;};
/* Single worker, authenticated decoded request. Duplicate reads reuse the last
 * final result; a BUSY read may be continued by the serialized worker. Stale or
 * changed duplicates and reentry do not call the player. No SQL or
 * reader handles here. Clear the whole ledger when the session is retired. */
int wr_library_dispatch(struct wr_library_ledger *,struct xw_player *,uint64_t,
                        const struct wr_library_request *,struct wr_library_reply *);
#endif
