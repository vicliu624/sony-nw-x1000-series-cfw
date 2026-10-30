#ifndef XNOW_PEER_H
#define XNOW_PEER_H
#include <stddef.h>
#include <stdint.h>
#define XNOW_PEER_LIMIT 20u
#define XNOW_ENCRYPTED_PEER_LIMIT 17u
enum xnow_peer_result {XNOW_PEER_OK=0,XNOW_PEER_END=1,XNOW_PEER_ARGUMENT=-1,XNOW_PEER_EXISTS=-2,XNOW_PEER_NOT_FOUND=-3,XNOW_PEER_FULL=-4,XNOW_PEER_CHANNEL=-5,XNOW_PEER_LENGTH=-6};
/* Version/channel are local compatibility policy, not an over-air negotiation.
 * Zero channel means current channel. LMK storage is volatile memory only;
 * storing a key does not claim CCMP is implemented in the radio backend. */
struct xnow_peer {uint8_t address[6],lmk[16],channel,version,encrypt;};
struct xnow_peer_table {struct xnow_peer peers[XNOW_PEER_LIMIT];uint8_t used[XNOW_PEER_LIMIT],encrypted_limit;};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_peer_init(struct xnow_peer_table *,unsigned encrypted_limit);
void xnow_peer_clear(struct xnow_peer_table *);
int xnow_peer_add(struct xnow_peer_table *,const struct xnow_peer *);
int xnow_peer_modify(struct xnow_peer_table *,const struct xnow_peer *);
int xnow_peer_delete(struct xnow_peer_table *,const uint8_t address[6]);
int xnow_peer_get(const struct xnow_peer_table *,const uint8_t address[6],struct xnow_peer *);
/* Cursor starts0; END leaves output unchanged. Get/next copies LMK as requested
 * configuration: callers must not log it and must erase temporary copies. */
int xnow_peer_next(const struct xnow_peer_table *,unsigned *cursor,struct xnow_peer *);
void xnow_peer_count(const struct xnow_peer_table *,unsigned *total,unsigned *encrypted);
int xnow_peer_validate_send(const struct xnow_peer_table *,const uint8_t address[6],unsigned current_channel,size_t bytes,struct xnow_peer *);
#ifdef __cplusplus
}
#endif
#endif
