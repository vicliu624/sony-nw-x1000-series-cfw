#ifndef WR_ARTWORK_CLIENT_H
#define WR_ARTWORK_CLIENT_H
#include "artwork_wire.h"

#define WR_ARTWORK_JOB_MS 120000u
#define WR_ARTWORK_REPLY_MS 2000u
#define WR_ARTWORK_PACE_MS 150u
#define WR_ARTWORK_BUSY_MS 300u
#define WR_ARTWORK_RETRY_MS 100u
#define WR_ARTWORK_UNAVAILABLE_MS 1000u
#define WR_ARTWORK_ATTEMPT_LIMIT 3u
#define WR_ARTWORK_UNAVAILABLE_LIMIT 5u
#define WR_ARTWORK_RESTART_LIMIT 2u

enum wr_artwork_observation {
    WR_ARTWORK_UNCHANGED,
    WR_ARTWORK_CONTEXT_CHANGED,
    WR_ARTWORK_OBSERVATION_PAUSED,
    WR_ARTWORK_OBSERVATION_RESUMED
};

/* Read-only progress for presentation/diagnostics. The client methods own all
 * transitions; a renderer must not edit pending requests or retry counters. */
struct wr_artwork_progress {
    struct xw_media_id id;
    uint64_t session, started, deadline, next;
    uint32_t serial, pending, received, total;
    unsigned attempts, complete, failed, identity_observed;
    int last_result;
    unsigned replies, timeouts, unavailable, restarts, local_rejects;
};
/* Large fixed buffer: allocate statically or in target PSRAM, not a task stack. */
struct wr_artwork_client {
    struct wr_artwork_progress job;
    unsigned char data[XW_ARTWORK_MAX];
};
#ifdef __cplusplus
extern "C" {
#endif
/* Missing identity in a live same-session observation pauses the job. A new
 * track/session or revoked connection invalidates it. No I/O occurs here. */
enum wr_artwork_observation wr_artwork_client_observe(struct wr_artwork_client *,
                                                      const struct wr_status *, int online,
                                                      uint64_t now);
const struct wr_artwork_progress *wr_artwork_client_progress(const struct wr_artwork_client *);
int wr_artwork_client_image_ready(const struct wr_artwork_client *);
int wr_artwork_client_request(struct wr_artwork_client *, uint64_t now, void *, size_t,
                              const uint8_t[32]);
int wr_artwork_client_accept(struct wr_artwork_client *, uint64_t now, const void *, size_t,
                             const uint8_t[32]);
void wr_artwork_client_tick(struct wr_artwork_client *, uint64_t now);
/* Local queue refusal retries a read identity, never a playback operation. */
void wr_artwork_client_send_rejected(struct wr_artwork_client *, uint64_t now);
/* Explicit user retry keeps the same-session serial monotonic. */
int wr_artwork_client_retry(struct wr_artwork_client *, uint64_t now);
#ifdef __cplusplus
}
#endif
#endif
