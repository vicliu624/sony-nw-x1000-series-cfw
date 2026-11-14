#ifndef WALKMAN_REMOTE_STATUS_AUTH_H
#define WALKMAN_REMOTE_STATUS_AUTH_H
#include "link.h"
#define WR_SIGNED_STATUS_BYTES (WR_STATUS_BYTES+16u)
/* Separate per-session 32-byte application key, not the ESP-NOW PMK/LMK.
 * HMAC-SHA256 truncated to 128 bits authenticates the exact WRS1 frame. */
#ifdef __cplusplus
extern "C" {
#endif
int wr_status_sign(void *,size_t,const struct wr_status *,const uint8_t key[32]);
/* Exact-length WRS2, or WRS1 when compact encoding would be larger.
 * Returns the authenticated frame length; old WRS1 remains accepted. */
#define WR_COMPACT_STATUS_MIN 68u
#define WR_HEARTBEAT_BYTES 36u
int wr_heartbeat_sign(void *,size_t,uint64_t,uint32_t,uint32_t,const uint8_t key[32]);
int wr_heartbeat_verify(uint64_t *,uint32_t *,uint32_t *,const void *,size_t,const uint8_t key[32]);
int wr_status_pack(void *,size_t,const struct wr_status *,const uint8_t key[32]);
int wr_status_frame(const void *,size_t);
int wr_status_verify(struct wr_status *,const void *,size_t,const uint8_t key[32]);
/* Application-internal authentication of bounded protocol bodies. */
int wr_auth_tag(uint8_t result[16],const void *,size_t,const uint8_t key[32]);
int wr_auth_check(const uint8_t expected[16],const void *,size_t,const uint8_t key[32]);
#ifdef __cplusplus
}
#endif
#endif
