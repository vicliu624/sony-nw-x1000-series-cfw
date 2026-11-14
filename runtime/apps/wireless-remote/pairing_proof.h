#ifndef WR_PAIRING_PROOF_H
#define WR_PAIRING_PROOF_H
#include <stdint.h>

enum wr_pairing_role { WR_PAIRING_WALKMAN=1, WR_PAIRING_CONTROLLER=2 };
#define WR_PAIRING_INVITE_BYTES 24u
#define WR_PAIRING_CONFIRM_BYTES 52u
struct wr_pairing_transcript {
 uint8_t walkman[6],controller[6],walkman_nonce[16],controller_nonce[16];
};
struct wr_pairing_keys {
 uint8_t auth[32],pmk[16],lmk[16];
 uint64_t session;
};
enum wr_walkman_pairing_phase { WR_PAIRING_CLOSED, WR_PAIRING_DISCOVERING, WR_PAIRING_OFFERED, WR_PAIRING_VERIFIED };
struct wr_walkman_pairing {
 struct wr_pairing_transcript transcript;
 uint8_t secret[16];
 uint8_t controller_public[32];
 uint64_t started_ms,seen_ms;
 unsigned phase,channel;
};
/* The secret must be generated with 128 bits of random entropy and transferred
 * out of band. This interface is not suitable for a short user-entered PIN.
 * Generate fresh nonces per attempt and call only after local confirmation. */
#ifdef __cplusplus
extern "C" {
#endif
int wr_pairing_invite(uint8_t out[WR_PAIRING_INVITE_BYTES],unsigned channel,const uint8_t nonce[16]);
int wr_pairing_invite_read(unsigned *channel,uint8_t nonce[16],const uint8_t in[WR_PAIRING_INVITE_BYTES]);
/* Stock text input provides UTF-16. Accept exactly 32 ASCII hex characters. */
int wr_pairing_parse_code(uint8_t out[16],const uint16_t *text,unsigned units);
int wr_pairing_confirmation(uint8_t out[WR_PAIRING_CONFIRM_BYTES],const uint8_t secret[16],
                            const struct wr_pairing_transcript *,enum wr_pairing_role);
int wr_pairing_confirmation_read(struct wr_pairing_keys *,const uint8_t in[WR_PAIRING_CONFIRM_BYTES],
                                 const uint8_t secret[16],const struct wr_pairing_transcript *,enum wr_pairing_role local_role);
/* Walkman requests a commit. Core2 emits its distinct receipt after saving. */
int wr_pairing_commit_encode(uint8_t out[WR_PAIRING_CONFIRM_BYTES],const struct wr_pairing_keys *,
                            const struct wr_pairing_transcript *,enum wr_pairing_role sender);
int wr_pairing_commit_check(const uint8_t in[WR_PAIRING_CONFIRM_BYTES],const struct wr_pairing_keys *,
                           const struct wr_pairing_transcript *,enum wr_pairing_role sender);
int wr_pairing_prove(uint8_t proof[16],const uint8_t secret[16],const struct wr_pairing_transcript *,enum wr_pairing_role);
int wr_pairing_finish(struct wr_pairing_keys *,const uint8_t proof[16],const uint8_t secret[16],
                      const struct wr_pairing_transcript *,enum wr_pairing_role local_role);
/* Caller supplies addresses and channel observed by its authorized radio owner.
 * A candidate is unauthenticated until the explicit offer/confirmation. */
int wr_walkman_pairing_open(struct wr_walkman_pairing *,const uint8_t local[6],unsigned channel,uint64_t now_ms);
int wr_walkman_pairing_observe(struct wr_walkman_pairing *,const uint8_t source[6],const uint8_t *,unsigned bytes,uint64_t now_ms);
int wr_walkman_pairing_offer(struct wr_walkman_pairing *,const uint8_t secret[16],const uint8_t nonce[16],
                            uint8_t out[WR_PAIRING_CONFIRM_BYTES],uint64_t now_ms);
int wr_walkman_pairing_confirm(struct wr_walkman_pairing *,const uint8_t source[6],const uint8_t *,unsigned bytes,
                              struct wr_pairing_keys *,uint64_t now_ms);
void wr_walkman_pairing_close(struct wr_walkman_pairing *);
#ifdef __cplusplus
}
#endif
#endif
