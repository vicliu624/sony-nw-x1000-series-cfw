#ifndef XNOW_FULL_H
#define XNOW_FULL_H
#include "xnow_mailbox.h"
#include "xnow_wire.h"
/* Experimental private full-radio backend, not the deployed fixed32 ABI.
 * Adapter must attest exact combined code/layout and serialize synchronous
 * command0x86 transactions. Addresses are radio CPU addresses, never host
 * pointers. No installation, reset or arbitrary-memory public SDK service. */
enum {XNOW_FULL_PROTECTED=3,XNOW_FULL_TX_PRE_MAC_REJECTED=2};
struct xnow_full_layout {uint32_t tx,rx,completion;};
struct xnow_full {struct xnow_word_io io;struct xnow_full_layout layout;uint32_t sequence,inflight;int fault,stopping;};
struct xnow_full_result {uint32_t token,stock_status,raw_fields;};
enum {XNOW_RX_BROADCAST=1u,XNOW_RX_AUTHENTICATED=2u};
/* Source ABI: rebuild consumers when this structure changes. AUTHENTICATED
 * means CCMP MIC and replay-state commit succeeded, never just peer membership.
 * BROADCAST is unauthenticated. No RSSI/channel values are fabricated. */
struct xnow_full_received {uint8_t source[6];struct xnow_wire_info info;uint32_t flags;};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_full_open(struct xnow_full *,const struct xnow_word_io *,const struct xnow_full_layout *);
int xnow_full_send(struct xnow_full *,const uint8_t destination[6],unsigned,const uint8_t random[4],const void *,size_t);
/* Experimental pre-encrypted frame path. local must be the adapter-verified
 * transmitter MAC: original header builder supplies that same actual source.
 * No CCMP/replay proof is inferred from IV shape or queue acceptance. */
int xnow_full_send_protected(struct xnow_full *,const uint8_t local[6],const uint8_t *frame,size_t);
int xnow_full_tx_result(struct xnow_full *,struct xnow_full_result *);
/* Canonical Action header plus retained body. Mutable duration/sequence/flags
 * are normalized; A3/fragment were validated on radio. local must be verified
 * by adapter. Ciphertext is not authenticated plaintext. */
int xnow_full_receive_action(struct xnow_full *,const uint8_t local[6],uint8_t *,size_t,size_t *);
int xnow_full_discard(struct xnow_full *);
int xnow_full_receive(struct xnow_full *,void *,size_t,struct xnow_full_received *);
/* Retry stop_step on PENDING; it closes RX, drains it and waits for original
 * TX completion. Never force-release submitted TX or reset after a timeout. */
int xnow_full_stop_step(struct xnow_full *);
#ifdef __cplusplus
}
#endif
#endif
