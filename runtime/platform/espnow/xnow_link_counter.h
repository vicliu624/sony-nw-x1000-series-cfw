#ifndef XNOW_LINK_COUNTER_H
#define XNOW_LINK_COUNTER_H

#include "xnow_link.h"
#include "xnow_security.h"

/* Volatile counters are valid only for a newly authenticated link key. Static
 * reusable keys retain the durable xnow_pn_file adapter. The caller drains and
 * forgets the old endpoint context before preparing another key epoch. */
struct xnow_link_counter {
    uint8_t tx_scope[32], rx_scope[32];
    uint64_t epoch, tx_highest, rx_highest;
    unsigned bound;
};

#ifdef __cplusplus
extern "C" {
#endif
/* Start with a fresh zeroed store. Accepts only the current negotiated INSTALL
 * serial. Keep the output descriptor separate from the store. Duplicate preparation
 * refuses rather than resetting counters. Output is unchanged on failure.
 * Keep this object alive until endpoint crypto and radio operations retire. */
int xnow_link_counter_prepare(struct xnow_link_counter *, const struct xnow_link *,
                             uint64_t key_serial, const uint8_t pmk[16],
                             struct xnow_security_io *);
/* Construct the callback descriptor without binding a key or resetting state.
 * All operations refuse until prepare authenticates a fresh key epoch. */
int xnow_link_counter_io(struct xnow_link_counter *,struct xnow_security_io *);
void xnow_link_counter_clear(struct xnow_link_counter *);
#ifdef __cplusplus
}
#endif
#endif
