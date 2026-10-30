#ifndef XNOW_SECURITY_H
#define XNOW_SECURITY_H
#include "xnow_pn.h"
#include "xnow_ccmp.h"
#include "xnow_wire.h"
enum xnow_security_result {XNOW_SECURITY_ARGUMENT=-20,XNOW_SECURITY_STORAGE=-21,XNOW_SECURITY_AUTH=-22,XNOW_SECURITY_REPLAY=-23,XNOW_SECURITY_FORMAT=-24,XNOW_SECURITY_CAPACITY=-25,XNOW_SECURITY_UNCERTAIN=-26};
struct xnow_security_io {
 void *context;
 int (*reserve_tx)(void *,const uint8_t[32],unsigned,uint64_t *,uint64_t *);
 int (*load_rx)(void *,const uint8_t[32],uint64_t *);
 /* Atomically persist pn only if greater than the current durable value.
  * Must confirm file/directory durability before success; never reset missing
  * records. Failure may be an ambiguous commit and faults this context. */
 int (*commit_rx)(void *,const uint8_t[32],uint64_t);
};
struct xnow_security {
 struct xnow_security_io io;struct xnow_pn tx;
 uint8_t key[16],local[6],peer[6],rx_scope[32];
 uint64_t rx_highest;unsigned key_id;int fault;unsigned espnow_profile;
};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_security_rx_scope(uint8_t out[32],const uint8_t local[6],const uint8_t peer[6],const uint8_t lmk[16]);
int xnow_security_init(struct xnow_security *,const struct xnow_security_io *,const uint8_t local[6],const uint8_t peer[6],const uint8_t lmk[16],unsigned key_id,unsigned pn_block);
/* Explicit measured S3 profile. key is AES(PMK,API LMK), ID3; same durable
 * wire-key PN namespace rules as the generic context. Rebuild consumers. */
int xnow_security_init_espnow(struct xnow_security *,const struct xnow_security_io *,const uint8_t local[6],const uint8_t peer[6],const uint8_t wire_key[16],unsigned pn_block);
void xnow_security_clear(struct xnow_security *);
int xnow_security_seal(struct xnow_security *,unsigned version,const uint8_t random[4],const void *,size_t,uint8_t *,size_t,size_t *);
/* No caller plaintext until MIC, complete ESP-NOW format and durable replay
 * commit succeed. A too-small output does not commit replay state. */
int xnow_security_open(struct xnow_security *,const uint8_t *,size_t,void *,size_t,struct xnow_wire_info *);
#ifdef __cplusplus
}
#endif
#endif
