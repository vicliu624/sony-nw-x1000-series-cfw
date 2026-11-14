#include "xnow_link_counter.h"
#include <string.h>

static void wipe(void *buffer, size_t bytes)
{
    volatile uint8_t *p = buffer;
    while (bytes--) *p++ = 0;
}

static int reserve(void *context, const uint8_t scope[32], unsigned count,
                    uint64_t *first, uint64_t *last)
{
    struct xnow_link_counter *store = context;
    if (!store || !store->bound || !scope || !first || !last || !count || count > 65536 ||
        memcmp(scope, store->tx_scope, 32)) return XNOW_PN_STORAGE;
    if (store->tx_highest > XNOW_PN_LIMIT - count) return XNOW_PN_EXHAUSTED;
    *first = store->tx_highest + 1;
    store->tx_highest += count;
    *last = store->tx_highest;
    return 0;
}

static int load(void *context, const uint8_t scope[32], uint64_t *highest)
{
    struct xnow_link_counter *store = context;
    if (!store || !store->bound || !scope || !highest ||
        memcmp(scope, store->rx_scope, 32)) return XNOW_PN_STORAGE;
    *highest = store->rx_highest;
    return 0;
}

static int commit(void *context, const uint8_t scope[32], uint64_t highest)
{
    struct xnow_link_counter *store = context;
    if (!store || !store->bound || !scope || memcmp(scope, store->rx_scope, 32) ||
        !highest || highest > XNOW_PN_LIMIT) return XNOW_PN_STORAGE;
    if (highest <= store->rx_highest) return XNOW_PN_REPLAY;
    store->rx_highest = highest;
    return 0;
}

int xnow_link_counter_io(struct xnow_link_counter *store,struct xnow_security_io *output)
{
    if(!store||!output)return XNOW_LINK_INVALID;
    *output=(struct xnow_security_io){store,reserve,load,commit};
    return 0;
}

int xnow_link_counter_prepare(struct xnow_link_counter *store, const struct xnow_link *link,
                             uint64_t serial, const uint8_t pmk[16],
                             struct xnow_security_io *output)
{
    if (!store || !link || !serial || !pmk || !output ||
        (store->bound && serial <= store->epoch)) return XNOW_LINK_INVALID;
    uint64_t pending = 0;
    uint8_t lmk[16], wire[16];
    int rc = xnow_link_key_pending(link, &pending, lmk);
    if (rc || pending != serial) { wipe(lmk, sizeof lmk); return XNOW_LINK_INVALID; }
    struct xnow_link_counter next;
    struct xnow_pn tx;
    memset(&next, 0, sizeof next);
    rc = xnow_ccmp_espnow_wire_key(pmk, lmk, wire);
    if (!rc) rc = xnow_pn_init(&tx, link->local, wire, 1024, store, reserve);
    if (!rc) {
        memcpy(next.tx_scope, tx.scope, 32);
        rc = xnow_security_rx_scope(next.rx_scope, link->local, link->peer, wire);
    }
    if (!rc && store->bound && (!memcmp(store->tx_scope, next.tx_scope, 32) ||
                               !memcmp(store->rx_scope, next.rx_scope, 32))) rc = XNOW_LINK_INVALID;
    wipe(lmk, sizeof lmk);
    wipe(wire, sizeof wire);
    wipe(&tx, sizeof tx);
    if (rc) { wipe(&next, sizeof next); return XNOW_LINK_INVALID; }
    next.epoch = serial;
    next.bound = 1;
    *store = next;
    (void)xnow_link_counter_io(store,output);
    wipe(&next, sizeof next);
    return 0;
}

void xnow_link_counter_clear(struct xnow_link_counter *store)
{
    if (store) wipe(store, sizeof *store);
}
