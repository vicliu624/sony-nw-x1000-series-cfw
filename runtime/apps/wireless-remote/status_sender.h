#ifndef WALKMAN_REMOTE_STATUS_SENDER_H
#define WALKMAN_REMOTE_STATUS_SENDER_H
#include "player_status.h"
#include "status_auth.h"
#include "control.h"
#include "mode_wire.h"
#include "session_wire.h"
#include "library_player.h"
#include "../../platform/player/provider.h"
#include "../../platform/espnow/xnow_client.h"
/* App-local composition of independent SDK clients, on one serialized worker.
 * The manager retains lifecycle ownership of both supplied services. */
struct wr_sender {
 struct xw_player *player;struct xnow_client *radio;
 uint8_t peer[6],key[32],wire[WR_SIGNED_STATUS_BYTES],incoming[XNOW_CLIENT_PAYLOAD_MAX];
 struct xw_player_snapshot snapshot;struct wr_status status;
 uint64_t session;uint32_t sequence,request;unsigned active,pending,submitted;
 struct wr_control_ledger ledger;uint8_t receipt[WR_CONTROL_BYTES];unsigned receipt_ready;
 uint8_t session_reply[WR_SESSION_BYTES];unsigned session_ready,session_replied;uint32_t session_sequence;
 struct wr_library_ledger library_ledger;uint8_t library_reply[WR_LIBRARY_REPLY_BYTES];unsigned library_ready;
 struct wr_library_request library_request;uint64_t library_started,library_next;unsigned library_active,library_clocked;
};
int wr_sender_init(struct wr_sender *,struct xw_player *,struct xnow_client *,const uint8_t peer[6],const uint8_t key[32],uint64_t session);
/* Read latest real snapshot and queue at most one status; busy never replays.
 * Caller schedules refresh/heartbeat, and stops on any negative result. */
int wr_sender_sample(struct wr_sender *);
int wr_sender_mode(struct wr_sender *,const struct wr_mode *);
/* One bounded radio-client step. ACK only admits TX; completion is separate.
 * Authenticated paired WRC1 controls dispatch once through the player SDK.
 * Receipts report SDK result, not observed playback. No automatic retry. */
int wr_sender_step(struct wr_sender *);
/* Continue only an admitted asynchronous read, at most once per100ms for2s.
 * No radio request replay and no calls after the manager begins teardown. */
int wr_sender_library_tick(struct wr_sender *,uint64_t now_ms);
/* Wipes app state only. Caller must close player session and drain/release radio
 * through its manager, including on original-player prepare/exit to Homebrew. */
void wr_sender_clear(struct wr_sender *);
#endif
