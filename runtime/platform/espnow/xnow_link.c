#include "xnow_link.h"
#include "../../native/sha256.h"
#include <string.h>

enum {
    WIRE_VERSION = 4, WIRE_KIND = 5, WIRE_SOURCE = 8, WIRE_DESTINATION = 14,
    WIRE_CLIENT_NONCE = 24, WIRE_ROOT_NONCE = 40, WIRE_TAG = 80,
    ATTEMPT_MILLISECONDS = 4000, RETRY_MILLISECONDS = 700, MAX_ATTEMPTS = 3
};
static const uint8_t wire_domain[] = "X1000-ESPNOW-LINK-WIRE-v1";
static const uint8_t key_domain[] = "X1000-ESPNOW-LINK-LMK-v1";

static void wipe(void *buffer, size_t bytes)
{
    volatile uint8_t *p = buffer;
    while (bytes--) *p++ = 0;
}

static int nonzero(const uint8_t *p, size_t bytes)
{
    unsigned value = 0;
    while (bytes--) value |= *p++;
    return value != 0;
}

static int equal(const uint8_t *a, const uint8_t *b, size_t bytes)
{
    unsigned difference = 0;
    while (bytes--) difference |= *a++ ^ *b++;
    return difference == 0;
}

static int unicast(const uint8_t address[6])
{
    return address && !(address[0] & 1) && nonzero(address, 6);
}

static int overlaps(const void *a, size_t a_bytes, const void *b, size_t b_bytes)
{
    uintptr_t left = (uintptr_t)a, right = (uintptr_t)b;
    return left <= right ? right - left < a_bytes : left - right < b_bytes;
}

/* Fixed 32-byte binding secret. Domain separation keeps these messages and
 * derived keys independent of pairing proofs and application authentication. */
static void authenticate(const uint8_t key[32], const uint8_t *domain, size_t domain_bytes,
                          const uint8_t *data, size_t bytes, uint8_t out[32])
{
    uint8_t pad[64], inner[32];
    for (unsigned i = 0; i < sizeof pad; i++) pad[i] = (i < 32 ? key[i] : 0) ^ 0x36;
    struct hb_sha256 hash;
    hb_sha256_init(&hash);
    hb_sha256_update(&hash, pad, sizeof pad);
    hb_sha256_update(&hash, domain, domain_bytes);
    hb_sha256_update(&hash, data, bytes);
    hb_sha256_final(&hash, inner);
    for (unsigned i = 0; i < sizeof pad; i++) pad[i] = (i < 32 ? key[i] : 0) ^ 0x5c;
    hb_sha256_init(&hash);
    hb_sha256_update(&hash, pad, sizeof pad);
    hb_sha256_update(&hash, inner, sizeof inner);
    hb_sha256_final(&hash, out);
    wipe(pad, sizeof pad);
    wipe(inner, sizeof inner);
    wipe(&hash, sizeof hash);
}

static int valid(const struct xnow_link *link)
{
    return link && link->initialized && !link->stopped;
}

static int clock_step(struct xnow_link *link, uint64_t now)
{
    if (!valid(link)) return XNOW_LINK_REVOKED;
    if (now < link->now || now > UINT64_MAX - ATTEMPT_MILLISECONDS) return XNOW_LINK_INVALID;
    link->now = now;
    return 0;
}

static int fresh_nonce(struct xnow_link *link, uint8_t out[16])
{
    uint8_t nonce[16] = {0};
    int failed = link->random(link->random_context, nonce, sizeof nonce);
    if (!valid(link)) { wipe(nonce, sizeof nonce); return XNOW_LINK_REVOKED; }
    failed = failed || !nonzero(nonce, sizeof nonce) ||
        equal(nonce, link->active_client, 16) || equal(nonce, link->active_root, 16) ||
        equal(nonce, link->client_nonce, 16) || equal(nonce, link->root_nonce, 16) ||
        equal(nonce, link->announcement, 16);
    if (!failed) memcpy(out, nonce, 16);
    wipe(nonce, sizeof nonce);
    return failed ? XNOW_LINK_ENTROPY : 0;
}

static void derive_key(struct xnow_link *link)
{
    uint8_t transcript[44], digest[32];
    const uint8_t *root = link->role == XNOW_LINK_ROOT ? link->local : link->peer;
    const uint8_t *controller = link->role == XNOW_LINK_CONTROLLER ? link->local : link->peer;
    memcpy(transcript, root, 6);
    memcpy(transcript + 6, controller, 6);
    memcpy(transcript + 12, link->client_nonce, 16);
    memcpy(transcript + 28, link->root_nonce, 16);
    authenticate(link->authentication, key_domain, sizeof key_domain - 1,
                 transcript, sizeof transcript, digest);
    memcpy(link->candidate_key, digest, 16);
    wipe(transcript, sizeof transcript);
    wipe(digest, sizeof digest);
}

static int queue(struct xnow_link *link, unsigned kind)
{
    if (link->tx_serial == UINT64_MAX) return XNOW_LINK_INVALID;
    uint8_t wire[XNOW_LINK_WIRE_BYTES] = {0}, digest[32];
    memcpy(wire, "XNL1", 4);
    wire[WIRE_VERSION] = 1;
    wire[WIRE_KIND] = (uint8_t)kind;
    memcpy(wire + WIRE_SOURCE, link->local, 6);
    memcpy(wire + WIRE_DESTINATION, link->peer, 6);
    if (kind == XNOW_LINK_ANNOUNCE) memcpy(wire + WIRE_ROOT_NONCE, link->announcement, 16);
    else {
        memcpy(wire + WIRE_CLIENT_NONCE, link->client_nonce, 16);
        if (kind != XNOW_LINK_HELLO) memcpy(wire + WIRE_ROOT_NONCE, link->root_nonce, 16);
    }
    authenticate(link->authentication, wire_domain, sizeof wire_domain - 1, wire, WIRE_TAG, digest);
    memcpy(wire + WIRE_TAG, digest, 16);
    memcpy(link->outbound, wire, sizeof wire);
    link->outbound_kind = kind;
    link->outgoing = 1;
    link->tx_serial++;
    wipe(wire, sizeof wire);
    wipe(digest, sizeof digest);
    return 0;
}

static void cancel_candidate(struct xnow_link *link)
{
    link->candidate = 0;
    link->phase = XNOW_LINK_IDLE;
    link->outgoing = 0;
    link->outbound_kind = 0;
    link->deadline = link->retry_at = 0;
    link->attempts = 0;
    wipe(link->client_nonce, 16);
    wipe(link->root_nonce, 16);
    wipe(link->candidate_key, 16);
    wipe(link->outbound, sizeof link->outbound);
}

static void begin_attempt(struct xnow_link *link, uint64_t now)
{
    link->candidate = 1;
    link->deadline = now + ATTEMPT_MILLISECONDS;
    link->retry_at = now + RETRY_MILLISECONDS;
    link->attempts = 1;
}

int xnow_link_init(struct xnow_link *link, enum xnow_link_role role,
                   const uint8_t local[6], const uint8_t peer[6],
                   const uint8_t authentication[32], void *context,
                   int (*random)(void *, uint8_t *, size_t))
{
    if (!link) return XNOW_LINK_INVALID;
    if (link->initialized) return XNOW_LINK_BUSY;
    if (!unicast(local) || !unicast(peer) || equal(local, peer, 6) ||
        !authentication || !nonzero(authentication, 32) || !random ||
        (role != XNOW_LINK_ROOT && role != XNOW_LINK_CONTROLLER)) return XNOW_LINK_INVALID;
    uint8_t input[44];
    memcpy(input, local, 6);
    memcpy(input + 6, peer, 6);
    memcpy(input + 12, authentication, 32);
    memset(link, 0, sizeof *link);
    memcpy(link->local, input, 6);
    memcpy(link->peer, input + 6, 6);
    memcpy(link->authentication, input + 12, 32);
    wipe(input, sizeof input);
    link->role = role;
    link->random_context = context;
    link->random = random;
    link->initialized = 1;
    return 0;
}

int xnow_link_announce(struct xnow_link *link, uint64_t now)
{
    int rc = clock_step(link, now);
    if (rc) return rc;
    if (link->role != XNOW_LINK_ROOT) return XNOW_LINK_INVALID;
    if (link->outgoing || link->candidate) return XNOW_LINK_BUSY;
    rc = fresh_nonce(link, link->announcement);
    return rc ? rc : queue(link, XNOW_LINK_ANNOUNCE);
}

int xnow_link_connect(struct xnow_link *link, uint64_t now)
{
    int rc = clock_step(link, now);
    if (rc) return rc;
    if (link->role != XNOW_LINK_CONTROLLER) return XNOW_LINK_INVALID;
    if (link->candidate) return XNOW_LINK_BUSY;
    uint8_t nonce[16];
    rc = fresh_nonce(link, nonce);
    if (rc) return rc;
    memcpy(link->client_nonce, nonce, 16);
    wipe(nonce, sizeof nonce);
    memset(link->root_nonce, 0, 16);
    begin_attempt(link, now);
    link->phase = XNOW_LINK_WAIT_OFFER;
    return queue(link, XNOW_LINK_HELLO);
}

static int decode(const struct xnow_link *link, const uint8_t source[6],
                   const uint8_t *wire, size_t bytes)
{
    if (!source || !wire || bytes != XNOW_LINK_WIRE_BYTES || memcmp(wire, "XNL1", 4) ||
        wire[WIRE_VERSION] != 1 || wire[6] || wire[7] || nonzero(wire + 20, 4) ||
        nonzero(wire + 56, 24) || !equal(source, link->peer, 6) ||
        !equal(wire + WIRE_SOURCE, link->peer, 6) ||
        !equal(wire + WIRE_DESTINATION, link->local, 6)) return XNOW_LINK_INVALID;
    unsigned kind = wire[WIRE_KIND];
    if (kind < XNOW_LINK_ANNOUNCE || kind > XNOW_LINK_READY) return XNOW_LINK_INVALID;
    int from_root = kind == XNOW_LINK_ANNOUNCE || kind == XNOW_LINK_OFFER || kind == XNOW_LINK_READY;
    if (from_root == (link->role == XNOW_LINK_ROOT)) return XNOW_LINK_INVALID;
    if (kind == XNOW_LINK_ANNOUNCE) {
        if (nonzero(wire + WIRE_CLIENT_NONCE, 16) || !nonzero(wire + WIRE_ROOT_NONCE, 16))
            return XNOW_LINK_INVALID;
    } else if (!nonzero(wire + WIRE_CLIENT_NONCE, 16) ||
               (kind == XNOW_LINK_HELLO ? nonzero(wire + WIRE_ROOT_NONCE, 16) :
                                        !nonzero(wire + WIRE_ROOT_NONCE, 16))) return XNOW_LINK_INVALID;
    uint8_t tag[32];
    authenticate(link->authentication, wire_domain, sizeof wire_domain - 1, wire, WIRE_TAG, tag);
    int correct = equal(tag, wire + WIRE_TAG, 16);
    wipe(tag, sizeof tag);
    return correct ? (int)kind : XNOW_LINK_AUTH;
}

int xnow_link_receive(struct xnow_link *link, const uint8_t source[6],
                      const void *input, size_t bytes, uint64_t now)
{
    if (link && input && overlaps(link, sizeof *link, input, bytes)) return XNOW_LINK_INVALID;
    int rc = clock_step(link, now);
    if (rc) return rc;
    const uint8_t *wire = input;
    int kind = decode(link, source, wire, bytes);
    if (kind < 0) return kind;
    if (link->candidate && now >= link->deadline) cancel_candidate(link);
    const uint8_t *client = wire + WIRE_CLIENT_NONCE, *root = wire + WIRE_ROOT_NONCE;
    if (kind == XNOW_LINK_ANNOUNCE) {
        if (equal(root, link->last_announcement, 16)) return XNOW_LINK_IGNORED;
        memcpy(link->last_announcement, root, 16);
        return link->candidate ? XNOW_LINK_IGNORED : xnow_link_connect(link, now);
    }
    if (kind == XNOW_LINK_HELLO) {
        /* The peer may reboot immediately after Ready, before sending data.
         * Only the committed retry transcript is superseded here; the active
         * key is retained until the new challenge is confirmed. */
        if (link->candidate && link->phase == XNOW_LINK_WAIT_PEER) {
            if (equal(client, link->active_client, 16)) return queue(link, XNOW_LINK_READY);
            cancel_candidate(link);
        }
        if (link->candidate) {
            if (!equal(client, link->client_nonce, 16)) return XNOW_LINK_BUSY;
            return link->phase == XNOW_LINK_WAIT_CONFIRM ? queue(link, XNOW_LINK_OFFER) : XNOW_LINK_IGNORED;
        }
        uint8_t nonce[16];
        rc = fresh_nonce(link, nonce);
        if (rc) return rc;
        memcpy(link->client_nonce, client, 16);
        memcpy(link->root_nonce, nonce, 16);
        wipe(nonce, sizeof nonce);
        derive_key(link);
        begin_attempt(link, now);
        link->phase = XNOW_LINK_WAIT_CONFIRM;
        return queue(link, XNOW_LINK_OFFER);
    }
    if (kind == XNOW_LINK_CONFIRM && link->active &&
        equal(client, link->active_client, 16) && equal(root, link->active_root, 16)) {
        /* An old confirmation may only request the same Ready response. */
        if (link->candidate && (!equal(link->client_nonce, link->active_client, 16) ||
                                !equal(link->root_nonce, link->active_root, 16)))
            return XNOW_LINK_IGNORED;
        memcpy(link->client_nonce, link->active_client, 16);
        memcpy(link->root_nonce, link->active_root, 16);
        return queue(link, XNOW_LINK_READY);
    }
    if (kind == XNOW_LINK_READY && link->active &&
        equal(client, link->active_client, 16) && equal(root, link->active_root, 16)) return XNOW_LINK_IGNORED;
    if (!link->candidate || !equal(client, link->client_nonce, 16)) return XNOW_LINK_IGNORED;
    if (kind == XNOW_LINK_OFFER) {
        if (link->phase == XNOW_LINK_WAIT_READY && equal(root, link->root_nonce, 16))
            return queue(link, XNOW_LINK_CONFIRM);
        if (link->phase != XNOW_LINK_WAIT_OFFER) return XNOW_LINK_IGNORED;
        memcpy(link->root_nonce, root, 16);
        derive_key(link);
        link->phase = XNOW_LINK_WAIT_READY;
        link->retry_at = now + RETRY_MILLISECONDS;
        link->attempts = 1;
        return queue(link, XNOW_LINK_CONFIRM);
    }
    if (!equal(root, link->root_nonce, 16)) return XNOW_LINK_IGNORED;
    if ((kind == XNOW_LINK_CONFIRM && link->phase == XNOW_LINK_WAIT_CONFIRM) ||
        (kind == XNOW_LINK_READY && link->phase == XNOW_LINK_WAIT_READY)) {
        if (link->key_serial == UINT64_MAX) return XNOW_LINK_INVALID;
        link->key_serial++;
        link->phase = XNOW_LINK_INSTALL;
        link->outgoing = 0;
        return XNOW_LINK_PENDING;
    }
    return XNOW_LINK_IGNORED;
}

int xnow_link_take(struct xnow_link *link, void *out, size_t bytes, unsigned *kind, uint64_t *ticket)
{
    if (!valid(link)) return XNOW_LINK_REVOKED;
    if (!out || bytes < XNOW_LINK_WIRE_BYTES || !kind || !ticket ||
        overlaps(link, sizeof *link, out, XNOW_LINK_WIRE_BYTES)) return XNOW_LINK_INVALID;
    if (!link->outgoing) return XNOW_LINK_IGNORED;
    memcpy(out, link->outbound, XNOW_LINK_WIRE_BYTES);
    *kind = link->outbound_kind;
    *ticket = link->tx_serial;
    link->outgoing = 0;
    return 0;
}

int xnow_link_resubmit(struct xnow_link *link, uint64_t ticket)
{
    if (!valid(link)) return XNOW_LINK_REVOKED;
    if (!ticket || ticket != link->tx_serial || !link->outbound_kind) return XNOW_LINK_INVALID;
    link->outgoing = 1;
    return 0;
}

int xnow_link_key_pending(const struct xnow_link *link, uint64_t *serial, uint8_t key[16])
{
    if (!valid(link)) return XNOW_LINK_REVOKED;
    if (!serial || !key || overlaps(link, sizeof *link, key, 16)) return XNOW_LINK_INVALID;
    if (link->phase != XNOW_LINK_INSTALL || !link->candidate) return XNOW_LINK_IGNORED;
    *serial = link->key_serial;
    memcpy(key, link->candidate_key, 16);
    return 0;
}

int xnow_link_key_installed(struct xnow_link *link, uint64_t serial, int success, uint64_t now)
{
    int rc = clock_step(link, now);
    if (rc) return rc;
    if (link->phase != XNOW_LINK_INSTALL || !link->candidate || serial != link->key_serial)
        return XNOW_LINK_INVALID;
    if (now >= link->deadline) { xnow_link_stop(link); return XNOW_LINK_EXPIRED; }
    if (success != 1) { xnow_link_stop(link); return XNOW_LINK_INSTALL_FAILED; }
    memcpy(link->active_client, link->client_nonce, 16);
    memcpy(link->active_root, link->root_nonce, 16);
    memcpy(link->active_key, link->candidate_key, 16);
    link->active = 1;
    link->active_serial = serial;
    link->active_confirmed = link->role == XNOW_LINK_CONTROLLER;
    if (link->role == XNOW_LINK_CONTROLLER) cancel_candidate(link);
    else {
        link->phase = XNOW_LINK_WAIT_PEER;
        link->deadline = now + ATTEMPT_MILLISECONDS;
        link->retry_at = now + RETRY_MILLISECONDS;
        link->attempts = 1;
        return queue(link, XNOW_LINK_READY);
    }
    return 0;
}

int xnow_link_tick(struct xnow_link *link, uint64_t now)
{
    int rc = clock_step(link, now);
    if (rc) return rc;
    if (!link->candidate) return 0;
    if (now >= link->deadline) { cancel_candidate(link); return XNOW_LINK_EXPIRED; }
    if (link->outgoing || now < link->retry_at || link->attempts >= MAX_ATTEMPTS) return 0;
    unsigned kind = link->phase == XNOW_LINK_WAIT_OFFER ? XNOW_LINK_HELLO :
                    link->phase == XNOW_LINK_WAIT_CONFIRM ? XNOW_LINK_OFFER :
                    link->phase == XNOW_LINK_WAIT_READY ? XNOW_LINK_CONFIRM :
                    link->phase == XNOW_LINK_WAIT_PEER ? XNOW_LINK_READY : 0;
    if (!kind) return 0;
    link->attempts++;
    link->retry_at = now + RETRY_MILLISECONDS;
    return queue(link, kind);
}

int xnow_link_data_ready(const struct xnow_link *link)
{
    return valid(link) && link->active && link->active_confirmed;
}

int xnow_link_peer_confirmed(struct xnow_link *link, uint64_t serial)
{
    if (!valid(link)) return XNOW_LINK_REVOKED;
    if (!link->active || !serial || serial != link->active_serial) return XNOW_LINK_IGNORED;
    link->active_confirmed = 1;
    if (link->phase == XNOW_LINK_WAIT_PEER) cancel_candidate(link);
    return 0;
}

void xnow_link_stop(struct xnow_link *link)
{
    if (!link) return;
    wipe(link->authentication, sizeof link->authentication);
    wipe(link->active_key, sizeof link->active_key);
    cancel_candidate(link);
    link->stopped = 1;
    link->active = 0;
    link->active_confirmed = 0;
}
