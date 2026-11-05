#ifndef WALKMAN_REMOTE_RECEIVER_H
#define WALKMAN_REMOTE_RECEIVER_H
#include "status_auth.h"
struct wr_receiver {uint8_t address[6],key[32];uint64_t session;uint32_t sequence;unsigned paired,have_status;struct wr_status status;uint8_t challenge[16],last_challenge[16];unsigned challenge_pending;};
#ifdef __cplusplus
extern "C" {
#endif
int wr_receiver_pair(struct wr_receiver *,const uint8_t address[6],const uint8_t key[32],uint64_t session);
int wr_receiver_accept(struct wr_receiver *,const uint8_t address[6],const void *,size_t);
void wr_receiver_clear(struct wr_receiver *);
int wr_receiver_challenge(struct wr_receiver *,const uint8_t[16],void *,size_t);
/* Returns1 for a new session,0 for the same session,-1 for refused input.
 * Same-session replies never reset status/sequence. No automatic rebinding
 * from ordinary status packets. Host and peer UI integration is separate. */
int wr_receiver_session_reply(struct wr_receiver *,const uint8_t[6],const void *,size_t);
void wr_receiver_cancel_challenge(struct wr_receiver *);
#ifdef __cplusplus
}
#endif
#endif
