#ifndef WR_PAIRING_AUTO_H
#define WR_PAIRING_AUTO_H
#include "pairing_proof.h"
#define WR_PAIR_AUTO_INVITE_BYTES 56u
#define WR_PAIR_AUTO_OFFER_BYTES 84u
#define WR_PAIR_AUTO_REPLY_BYTES 52u
#define WR_PAIR_AUTO_FRAME_MAX 84u
/* Selection-based ephemeral X25519 pairing. The first exchange has no OOB
 * identity authentication. Both peers must explicitly be in pairing mode;
 * selection is local user intent, never permission to replace an old binding. */
#ifdef __cplusplus
extern "C" {
#endif
int wr_pair_curve_public(uint8_t[32],const uint8_t[32]);
int wr_pair_curve_self_test(void);
int wr_pair_curve_shared(uint8_t[32],const uint8_t[32],const uint8_t[32]);
int wr_pair_auto_invite(uint8_t[WR_PAIR_AUTO_INVITE_BYTES],unsigned,const uint8_t[16],const uint8_t[32]);
int wr_walkman_pair_auto_observe(struct wr_walkman_pairing *,const uint8_t[6],const uint8_t *,unsigned,uint64_t);
int wr_walkman_pair_auto_offer(struct wr_walkman_pairing *,const uint8_t[32],const uint8_t[16],uint8_t[WR_PAIR_AUTO_OFFER_BYTES],uint64_t);
int wr_pair_auto_offer_read(struct wr_pairing_keys *,uint8_t[16],const uint8_t[WR_PAIR_AUTO_OFFER_BYTES],const uint8_t[32],const uint8_t[32],const struct wr_pairing_transcript *);
int wr_pair_auto_reply(uint8_t[WR_PAIR_AUTO_REPLY_BYTES],const uint8_t[16],const struct wr_pairing_transcript *);
int wr_walkman_pair_auto_confirm(struct wr_walkman_pairing *,const uint8_t[6],const uint8_t *,unsigned,struct wr_pairing_keys *,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
