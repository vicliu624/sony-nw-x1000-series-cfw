#ifndef WR_RUN_PROFILE_H
#define WR_RUN_PROFILE_H
#include <stdint.h>
/* Pairing-only clean retirement diagnostic. Four saturating seven-bit counts. */
#define WR_PAIRING_RX_SUMMARY_TAG 0x60000000u
/* Four four-bit counts, eight-bit listening seconds and four-bit stop cause. */
#define WR_PAIRING_RX_TIMED_TAG 0x70000000u
#define WR_PAIRING_RX_SUMMARY_MASK 0xf0000000u
#define WR_PAIRING_RUNTIME_ERROR_TAG 0x50000000u
#include <stddef.h>
#define WR_RADIO_PAIRING_STORAGE (-4001)
#define WR_PAIRING_RECORD_BYTES 112u
struct wr_pairing_keys;
int wr_run_seed_valid(const uint8_t seed[80]);
int wr_pairing_record_encode(uint8_t out[WR_PAIRING_RECORD_BYTES],const uint8_t peer[6],
                             const struct wr_pairing_keys *,const uint8_t cookie[16]);
/* Same record for the supervisor and the RF owner. Either output can be omitted. */
int wr_pairing_record_read(const uint8_t record[WR_PAIRING_RECORD_BYTES],const uint8_t expected_peer[6],
                           uint8_t config[80],uint8_t radio_keys[32]);
/* Trusted template after file/volume qualification. Success creates a RAM-only
 * run config; failure preserves output. Entropy must fill all requested bytes. */
int wr_run_profile(uint8_t[80],const uint8_t[80],uint64_t,void *,int (*)(void *,uint8_t *,size_t));
/* Only after authenticated retirement and EOF. A channel change can end a
 * shared remote while leaving the native Wi-Fi driver running. */
int wr_run_recoverable_retirement(int shared,int failure,int service_status,int owner_status);
#endif
