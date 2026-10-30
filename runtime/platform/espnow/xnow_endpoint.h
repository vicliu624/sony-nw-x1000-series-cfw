#ifndef XNOW_ENDPOINT_H
#define XNOW_ENDPOINT_H
#include "xnow_full.h"
#include "xnow_peer.h"
enum xnow_endpoint_error {XNOW_ENDPOINT_PEER=-20,XNOW_ENDPOINT_CHANNEL=-21,XNOW_ENDPOINT_LENGTH=-22,XNOW_ENDPOINT_CRYPTO_UNAVAILABLE=-23};
/* Native polling owner. All APIs serialized; callbacks must not reenter owner.
 * RNG must fill four fresh bytes; no time/counter/random fallback is supplied.
 * No installed device adapter is supplied; encryption uses an optional native adapter. */
struct xnow_endpoint_crypto {
 void *context;
 int (*prepare)(void *,const struct xnow_peer *);
 int (*send)(void *,struct xnow_full *,const uint8_t[6],unsigned,const uint8_t[4],const void *,size_t);
 int (*receive)(void *,struct xnow_full *,void *,size_t,struct xnow_full_received *);
 void (*forget)(void *,const uint8_t[6]);
 void (*clear)(void *);
};
struct xnow_endpoint {
 struct xnow_full *transport;struct xnow_peer_table peers;
 void *random_context;int (*random)(void *,uint8_t[4]);
 struct xnow_endpoint_crypto crypto;
 uint8_t targets[XNOW_PEER_LIMIT][6],versions[XNOW_PEER_LIMIT],encrypted[XNOW_PEER_LIMIT];
 uint8_t payload[XNOW_ESPNOW_V2_MAX];size_t bytes;
 unsigned channel,count,index;int waiting,active,stopping;
};
struct xnow_endpoint_result {uint8_t destination[6];int result;uint32_t stock_status,raw_fields;};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_endpoint_init(struct xnow_endpoint *,struct xnow_full *,unsigned channel,unsigned encrypted_limit,void *,int (*random)(void *,uint8_t[4]));
int xnow_endpoint_add(struct xnow_endpoint *,const struct xnow_peer *);
int xnow_endpoint_modify(struct xnow_endpoint *,const struct xnow_peer *);
int xnow_endpoint_delete(struct xnow_endpoint *,const uint8_t[6]);
/* NULL destination snapshots all registered peers. Validates the complete batch
 * before any send; copies data before return. Encrypted peers are never sent
 * in plaintext. Advance with poll; one MAC send at a time, no automatic retry. */
int xnow_endpoint_send(struct xnow_endpoint *,const uint8_t destination[6],const void *,size_t);
/* OK yields exactly one result. AGAIN means idle, PENDING means queued/waiting.
 * stock_status is MAC raw0/1 or PRE_MAC_REJECTED2; no physical ACK claim. */
int xnow_endpoint_poll(struct xnow_endpoint *,struct xnow_endpoint_result *);
int xnow_endpoint_receive(struct xnow_endpoint *,void *,size_t,struct xnow_full_received *);
/* Cancels unsent batch entries, waits submitted send and drains RX, then wipes
 * peers/payload. Success is ownership drain, not proof all radio tasks quiesced. */
int xnow_endpoint_stop_step(struct xnow_endpoint *);
#ifdef __cplusplus
}
#endif
#endif
