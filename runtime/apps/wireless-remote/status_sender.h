#ifndef WALKMAN_REMOTE_STATUS_SENDER_H
#define WALKMAN_REMOTE_STATUS_SENDER_H
#include "player_status.h"
#include "status_auth.h"
#include "control.h"
#include "mode_wire.h"
#include "session_wire.h"
#include "library_player.h"
#include "artwork_wire.h"
#include "../../platform/player/provider.h"
#include "../../platform/espnow/xnow_client.h"
/* App-local composition of independent SDK clients, on one serialized worker.
 * The manager retains lifecycle ownership of both supplied services. */
struct wr_sender {
    struct xw_player *player;
    struct xnow_client *radio;
    uint8_t peer[6], key[32], wire[WR_SIGNED_STATUS_BYTES], incoming[XNOW_CLIENT_PAYLOAD_MAX];
    struct xw_player_snapshot snapshot;
    struct wr_status status;
    uint64_t session;
    uint32_t sequence, request;
    unsigned active, pending, submitted;
    uint64_t now, last_status_at;
    unsigned have_status, force_status;
    uint32_t resync_serial, snapshot_sequence;
    uint32_t mode_refresh_serial;
    struct wr_control_ledger ledger;
    uint8_t receipt[WR_CONTROL_BYTES];
    unsigned receipt_ready;
    uint8_t session_reply[WR_SESSION_BYTES];
    unsigned session_ready, session_replied;
    uint32_t session_sequence;
    struct wr_library_ledger library_ledger;
    uint8_t library_reply[WR_LIBRARY_REPLY_BYTES];
    unsigned library_ready;
    struct wr_library_request library_request;
    uint64_t library_started, library_next;
    unsigned library_active, library_clocked;
    struct wr_artwork_request artwork_request;
    struct xw_artwork_chunk artwork_source;
    uint32_t artwork_serial, artwork_next, artwork_total;
    uint8_t artwork_reply[WR_ARTWORK_REPLY_MAX];
    unsigned artwork_reply_bytes, artwork_ready, artwork_active; /* pieces left to prepare */
    void *artwork_context;
    int (*artwork_read)(void *, uint32_t, struct xw_artwork_chunk *);
    void *source_context;
    int (*source_alive)(void *);
#ifdef WR_RADIO_BENCHMARK
    struct {
        uint32_t run, bytes, frames, failed, tx_wait_ms;
        uint64_t started, queued_at;
        unsigned finishing;
    } bench;
#endif
};
int wr_sender_init(struct wr_sender *, struct xw_player *, struct xnow_client *,
                   const uint8_t peer[6], const uint8_t key[32], uint64_t session);
/* Read latest real snapshot and queue at most one changed/requested status.
 * Unchanged state stays silent; caller stops on a negative result. */
int wr_sender_sample(struct wr_sender *);
int wr_sender_mode(struct wr_sender *, const struct wr_mode *);
/* One bounded radio-client step. ACK only admits TX; completion is separate.
 * Authenticated paired WRC1 controls dispatch once through the player SDK.
 * Receipts report SDK result, not observed playback. No automatic retry. */
int wr_sender_step(struct wr_sender *);
/* Continue only an admitted asynchronous read, at most once per100ms for2s.
 * No radio request replay and no calls after the manager begins teardown. */
int wr_sender_library_tick(struct wr_sender *, uint64_t now_ms);
int wr_sender_artwork_tick(struct wr_sender *);
/* Wipes app state only. Caller must close player session and drain/release radio
 * through its manager, including on original-player prepare/exit to Homebrew. */
void wr_sender_clear(struct wr_sender *);
#endif
