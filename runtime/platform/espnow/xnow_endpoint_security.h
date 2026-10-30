#ifndef XNOW_ENDPOINT_SECURITY_H
#define XNOW_ENDPOINT_SECURITY_H
#include "xnow_endpoint.h"
#include "xnow_security.h"
struct xnow_endpoint_security {
 struct xnow_endpoint *endpoint;struct xnow_security_io io;
 uint8_t local[6],used[XNOW_PEER_LIMIT];unsigned block;
 struct xnow_security contexts[XNOW_PEER_LIMIT];
 uint8_t received[XNOW_CCMP_FRAME_MAX];size_t received_bytes;
 uint8_t pmk[16];unsigned espnow_profile;
};
#ifdef __cplusplus
extern "C" {
#endif
/* Configure once on an idle endpoint with no peers. local must be verified by
 * device adapter. Storage must already provision scopes for proven fresh keys
 * or load existing counters. No implicit key/PN reset. Workspace lifetime must
 * cover endpoint; stop/peer replacement erase contexts. No device installation.
 * Receive normalizes rejected plaintext wire bodies to SECURITY_FORMAT, not raw
 * wire error integers that collide with backend IO/UNCERTAIN. Device/storage
 * errors retain their respective failure semantics. */
/* Plaintext broadcast remains receivable from an encrypted-unicast peer;
 * broadcasts are unauthenticated. Plaintext unicast from that peer is rejected.
 * Peer membership alone never authenticates a broadcast's claimed source. */
int xnow_endpoint_security_attach(struct xnow_endpoint *,struct xnow_endpoint_security *,const uint8_t local[6],unsigned pn_block,const struct xnow_security_io *);
/* API peer LMKs are mapped to the observed effective wire keys with this PMK.
 * Provision/journal scopes for wire keys, not raw API LMKs. Explicit profile;
 * generic behavior and frozen source archives are unchanged. */
int xnow_endpoint_security_attach_espnow(struct xnow_endpoint *,struct xnow_endpoint_security *,const uint8_t local[6],const uint8_t pmk[16],unsigned pn_block,const struct xnow_security_io *);
#ifdef __cplusplus
}
#endif
#endif
