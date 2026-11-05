#ifndef WALKMAN_REMOTE_LIBRARY_WIRE_H
#define WALKMAN_REMOTE_LIBRARY_WIRE_H
#include "status_auth.h"
#include "../../platform/player/player.h"
/* One complete metadata item per bounded response; no database paths on wire.
 * Caller correlates session/request and serializes browse with player teardown.
 * This is app protocol, not a generic SDK transport or playlist classification. */
#define WR_LIBRARY_REQUEST_BYTES 120u
#define WR_LIBRARY_REPLY_BYTES (48u+WR_STATUS_BYTES+16u)
struct wr_library_request {uint64_t session;uint32_t request;struct xw_media_query query;};
struct wr_library_reply {uint64_t session;uint32_t request;int32_t result;struct xw_media_page page;struct xw_media_item item;};
#ifdef __cplusplus
extern "C" {
#endif
int wr_library_request_encode(void *,size_t,const struct wr_library_request *,const uint8_t[32]);
int wr_library_request_decode(struct wr_library_request *,const void *,size_t,const uint8_t[32]);
int wr_library_reply_encode(void *,size_t,const struct wr_library_reply *,const uint8_t[32]);
int wr_library_reply_decode(struct wr_library_reply *,const void *,size_t,const uint8_t[32]);
#ifdef __cplusplus
}
#endif
#endif
