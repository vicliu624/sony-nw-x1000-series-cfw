#include "xnow_owner_link.h"
#include <string.h>

static const uint8_t broadcast[6] = {255, 255, 255, 255, 255, 255};

static void wipe(void *buffer, size_t bytes) {
    volatile uint8_t *p = buffer;
    while (bytes--)
        *p++ = 0;
}

static int canceled(const struct xnow_owner_link *owner) {
    return owner->stopped || (owner->cancel && *owner->cancel);
}

static int data_ready(void *context) {
    const struct xnow_owner_link *owner = context;
    return owner->initialized && !canceled(owner) && !owner->link.candidate &&
           xnow_link_data_ready(&owner->link);
}

static int current_time(struct xnow_owner_link *owner, uint64_t *now) {
    return owner->clock(owner->clock_context, now) ? XNOW_IO : 0;
}

static int install_key(struct xnow_owner_link *owner, uint64_t serial, const uint8_t key[16]) {
    struct xnow_endpoint *endpoint = owner->endpoint;
    if (endpoint->active || endpoint->transport->inflight)
        return XNOW_PENDING;
    if (canceled(owner))
        return XNOW_PENDING;
    struct xnow_security_io io;
    int result = xnow_link_counter_prepare(&owner->counters, &owner->link, serial, owner->pmk, &io);
    struct xnow_peer peer;
    memset(&peer, 0, sizeof peer);
    memcpy(peer.address, owner->link.peer, 6);
    peer.channel = endpoint->channel;
    peer.version = 2;
    peer.encrypt = 1;
    memcpy(peer.lmk, key, 16);
    if (!result)
        result = xnow_endpoint_modify(endpoint, &peer);
    if (!result)
        result = endpoint->crypto.prepare(endpoint->crypto.context, &peer);
    wipe(&peer, sizeof peer);
    uint64_t now;
    if (current_time(owner, &now))
        return XNOW_IO;
    if (canceled(owner))
        return XNOW_PENDING;
    int installed = xnow_link_key_installed(&owner->link, serial, result == 0, now);
    if (result || installed != XNOW_LINK_OK)
        return result ? result : installed < 0 ? installed : XNOW_UNCERTAIN;
    owner->installed++;
    return 0;
}

static int idle_step(void *context, struct xnow_endpoint *endpoint) {
    struct xnow_owner_link *owner = context;
    if (!owner->initialized || endpoint != owner->endpoint)
        return XNOW_IDENTITY;
    if (canceled(owner))
        return XNOW_PENDING;
    uint64_t now;
    if (current_time(owner, &now))
        return XNOW_IO;
    int result = xnow_link_tick(&owner->link, now);
    if (result < 0)
        return result;
    if (owner->tx_active) {
        struct xnow_endpoint_result done;
        result = xnow_endpoint_poll(endpoint, &done);
        if (result == XNOW_PENDING)
            return XNOW_PENDING;
        if (result)
            return result == XNOW_AGAIN ? XNOW_UNCERTAIN : result;
        if (!endpoint->active)
            owner->tx_active = 0;
        /* Peer responses and bounded protocol retries determine progress.
         * A MAC failure is not permission to regenerate a nonce or key. */
        return XNOW_PENDING;
    }
    if (endpoint->active || endpoint->transport->inflight)
        return XNOW_UNCERTAIN;
    uint64_t serial;
    uint8_t key[16];
    result = xnow_link_key_pending(&owner->link, &serial, key);
    if (!result) {
        result = install_key(owner, serial, key);
        wipe(key, sizeof key);
        if (result)
            return result;
    } else if (result != XNOW_LINK_IGNORED)
        return result;
    if (canceled(owner))
        return XNOW_PENDING;
    uint8_t wire[XNOW_LINK_WIRE_BYTES];
    unsigned kind;
    uint64_t ticket;
    result = xnow_link_take(&owner->link, wire, sizeof wire, &kind, &ticket);
    if (result == XNOW_LINK_IGNORED)
        return 0;
    if (result)
        return result;
    result = xnow_endpoint_send(endpoint, broadcast, wire, sizeof wire);
    wipe(wire, sizeof wire);
    if (result)
        return result;
    owner->tx_active = 1;
    owner->tx_ticket = ticket;
    owner->transmitted++;
    return XNOW_PENDING;
}

static int receive_frame(void *context, const struct xnow_full_received *event, const uint8_t *data,
                         size_t bytes) {
    struct xnow_owner_link *owner = context;
    if (!owner->initialized)
        return XNOW_IDENTITY;
    if (canceled(owner))
        return 1;
    if (bytes >= 4 && !memcmp(data, "XNL1", 4)) {
        owner->received++;
        if (event->flags != XNOW_RX_BROADCAST || memcmp(event->source, owner->link.peer, 6)) {
            owner->rejected++;
            return 1;
        }
        uint64_t now;
        if (current_time(owner, &now))
            return XNOW_IO;
        int result = xnow_link_receive(&owner->link, event->source, data, bytes, now);
        if (result < 0)
            owner->rejected++;
        /* Invalid broadcasts cannot stop an authenticated existing link. */
        return 1;
    }
    if (event->flags == XNOW_RX_AUTHENTICATED && !memcmp(event->source, owner->link.peer, 6) &&
        owner->link.active) {
        (void)xnow_link_peer_confirmed(&owner->link, owner->link.active_serial);
        return 0;
    }
    return 1;
}

static void stopping(void *context) {
    struct xnow_owner_link *owner = context;
    owner->stopped = 1;
    xnow_link_stop(&owner->link);
}

int xnow_owner_link_prepare(struct xnow_owner_link *owner, struct xnow_endpoint *endpoint,
                            struct xnow_endpoint_security *security, const uint8_t local[6],
                            const uint8_t peer_address[6], const uint8_t authentication[32],
                            const uint8_t pmk[16], void *random_context,
                            int (*random)(void *, uint8_t *, size_t), void *clock_context,
                            int (*clock)(void *, uint64_t *), const volatile int *cancel) {
    if (!owner || owner->initialized || owner->stopped || !endpoint || !endpoint->transport ||
        !security || security->endpoint || !pmk || !clock || !cancel || *cancel ||
        endpoint->active || endpoint->stopping || endpoint->crypto.context ||
        endpoint->transport->fault || endpoint->transport->stopping ||
        endpoint->transport->inflight)
        return XNOW_ARGUMENT;
    int result = xnow_link_init(&owner->link, XNOW_LINK_ROOT, local, peer_address, authentication,
                                random_context, random);
    if (result)
        return result;
    owner->endpoint = endpoint;
    owner->security = security;
    owner->clock = clock;
    owner->clock_context = clock_context;
    owner->cancel = cancel;
    memcpy(owner->pmk, pmk, 16);
    struct xnow_security_io io;
    result = xnow_link_counter_io(&owner->counters, &io);
    if (!result)
        result = xnow_endpoint_security_attach_espnow(endpoint, security, local, pmk, 1024, &io);
    struct xnow_peer peer;
    memset(&peer, 0, sizeof peer);
    peer.channel = endpoint->channel;
    peer.version = 2;
    memcpy(peer.address, broadcast, 6);
    if (!result)
        result = xnow_endpoint_add(endpoint, &peer);
    memcpy(peer.address, peer_address, 6);
    if (!result)
        result = xnow_endpoint_add(endpoint, &peer);
    wipe(&peer, sizeof peer);
    uint64_t now;
    if (!result)
        result = current_time(owner, &now);
    if (!result && !canceled(owner))
        result = xnow_link_announce(&owner->link, now);
    if (result)
        return result;
    owner->initialized = 1;
    return 0;
}

int xnow_owner_link_transport(struct xnow_owner_link *owner, struct xnow_owner_transport *output) {
    if (!owner || !output)
        return XNOW_ARGUMENT;
    *output = (struct xnow_owner_transport){owner, data_ready, idle_step, receive_frame, stopping};
    return 0;
}

int xnow_owner_link_clear(struct xnow_owner_link *owner) {
    if (!owner)
        return XNOW_ARGUMENT;
    stopping(owner);
    if (owner->endpoint && (owner->endpoint->active || owner->endpoint->transport->inflight ||
                            (owner->security && owner->security->endpoint)))
        return XNOW_PENDING;
    xnow_link_counter_clear(&owner->counters);
    wipe(owner, sizeof *owner);
    return 0;
}
