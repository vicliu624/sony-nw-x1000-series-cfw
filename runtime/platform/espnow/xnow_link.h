#ifndef XNOW_LINK_H
#define XNOW_LINK_H

#include <stddef.h>
#include <stdint.h>

/* Authenticated link-key negotiation, independent of radio ownership and player
 * protocols. The caller supplies entropy, transport and serialized peer-key IO. */
#define XNOW_LINK_WIRE_BYTES 96u
#define XNOW_LINK_NONCE_BYTES 16u

enum xnow_link_role { XNOW_LINK_ROOT = 1, XNOW_LINK_CONTROLLER = 2 };
enum xnow_link_message {
    XNOW_LINK_ANNOUNCE = 1, XNOW_LINK_HELLO, XNOW_LINK_OFFER,
    XNOW_LINK_CONFIRM, XNOW_LINK_READY
};
enum xnow_link_phase {
    XNOW_LINK_IDLE, XNOW_LINK_WAIT_OFFER, XNOW_LINK_WAIT_CONFIRM,
    XNOW_LINK_WAIT_READY, XNOW_LINK_INSTALL, XNOW_LINK_WAIT_PEER
};
enum xnow_link_result {
    XNOW_LINK_OK = 0, XNOW_LINK_PENDING = 1, XNOW_LINK_IGNORED = 2,
    XNOW_LINK_EXPIRED = 3, XNOW_LINK_INVALID = -1, XNOW_LINK_AUTH = -2,
    XNOW_LINK_BUSY = -3, XNOW_LINK_ENTROPY = -4, XNOW_LINK_REVOKED = -5,
    XNOW_LINK_INSTALL_FAILED = -6
};

struct xnow_link {
    uint8_t local[6], peer[6], authentication[32];
    uint8_t client_nonce[16], root_nonce[16], candidate_key[16];
    uint8_t active_client[16], active_root[16], active_key[16];
    uint8_t announcement[16], last_announcement[16], outbound[XNOW_LINK_WIRE_BYTES];
    void *random_context;
    int (*random)(void *, uint8_t *, size_t);
    uint64_t now, deadline, retry_at, key_serial, active_serial, tx_serial;
    unsigned role, phase, initialized, stopped, active, active_confirmed;
    unsigned candidate, outbound_kind, outgoing, attempts;
};

#ifdef __cplusplus
extern "C" {
#endif
/* Fresh zeroed object only. A stopped object may be reset only after its caller
 * independently completes radio/peer cleanup. Do not copy a live context. */
int xnow_link_init(struct xnow_link *, enum xnow_link_role,
                   const uint8_t local[6], const uint8_t peer[6],
                   const uint8_t authentication[32], void *,
                   int (*random)(void *, uint8_t *, size_t));
/* Explicit startup/demand only. No background heartbeat is created. */
int xnow_link_announce(struct xnow_link *, uint64_t now_ms);
int xnow_link_connect(struct xnow_link *, uint64_t now_ms);
int xnow_link_receive(struct xnow_link *, const uint8_t source[6],
                      const void *, size_t, uint64_t now_ms);
int xnow_link_tick(struct xnow_link *, uint64_t now_ms);
/* Copy one pending plaintext broadcast. A failed submission may put the same
 * immutable response back; it must not regenerate nonces or reinstall a key. */
int xnow_link_take(struct xnow_link *, void *, size_t, unsigned *kind, uint64_t *ticket);
int xnow_link_resubmit(struct xnow_link *, uint64_t ticket);
/* The caller drains submitted radio TX before changing the peer key. A serial
 * identifies this exact key installation; completion after stop is rejected.
 * success must be exactly 1; native error codes must not be passed as booleans. */
int xnow_link_key_pending(const struct xnow_link *, uint64_t *serial, uint8_t key[16]);
int xnow_link_key_installed(struct xnow_link *, uint64_t serial, int success,
                           uint64_t now_ms);
int xnow_link_data_ready(const struct xnow_link *);
int xnow_link_peer_confirmed(struct xnow_link *, uint64_t active_key_serial);
/* Stops negotiation and erases secrets; does not claim radio retirement. */
void xnow_link_stop(struct xnow_link *);
#ifdef __cplusplus
}
#endif
#endif
