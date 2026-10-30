#ifndef XNOW_CCMP_H
#define XNOW_CCMP_H
#include <stddef.h>
#include <stdint.h>
#define XNOW_CCMP_FRAME_MAX 1560u
#define XNOW_CCMP_PN_MAX UINT64_C(0xffffffffffff)
enum xnow_ccmp_result {XNOW_CCMP_OK=0,XNOW_CCMP_ARGUMENT=-1,XNOW_CCMP_FORMAT=-2,XNOW_CCMP_CAPACITY=-3,XNOW_CCMP_AUTH=-4,XNOW_CCMP_REPLAY=-5,XNOW_CCMP_ALIAS=-6};
#ifdef __cplusplus
extern "C" {
#endif
/* Explicit ESP-NOW hardware profile observed on S3/IDF5.5.1: nonce0 and
 * legacy subtype-masked AAD, MIC8 always checked. key is the effective wire
 * key, not automatically the API LMK. These do not select/reset a PN namespace.
 * One33-byte physical vector qualified; broad interoperability is pending. */
int xnow_ccmp_espnow_wire_key(const uint8_t pmk[16],const uint8_t api_lmk[16],uint8_t out[16]);
int xnow_ccmp_espnow_seal(const uint8_t wire_key[16],unsigned key_id,uint64_t pn,const uint8_t *,size_t,uint8_t *,size_t,size_t *);
int xnow_ccmp_espnow_open(const uint8_t wire_key[16],unsigned key_id,uint64_t *highest,const uint8_t *,size_t,uint8_t *,size_t,size_t *);
/* Standard nonfragmented unicast Action CCMP-128 framing, no FCS.
 * BearSSL constant-time AES backend; not yet ESP-device-qualified.
 * Caller MUST allocate each PN once per transmitter/key, across sessions.
 * This primitive does not invent a safe PN seed, persist counters, wrap LMKs,
 * negotiate keys or allow encrypted multicast. Inputs/outputs cannot overlap.
 * Failure leaves output, length and receive replay counter unchanged. */
int xnow_ccmp_seal(const uint8_t key[16],unsigned key_id,uint64_t pn,const uint8_t *plain,size_t n,uint8_t *out,size_t capacity,size_t *written);
int xnow_ccmp_open(const uint8_t key[16],unsigned key_id,uint64_t *highest_pn,const uint8_t *frame,size_t n,uint8_t *out,size_t capacity,size_t *written);
#ifdef __cplusplus
}
#endif
#endif
