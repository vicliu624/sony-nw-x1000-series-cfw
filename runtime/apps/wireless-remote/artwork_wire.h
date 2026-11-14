#ifndef WR_ARTWORK_WIRE_H
#define WR_ARTWORK_WIRE_H
#include "status_auth.h"
#include "../../platform/player/artwork.h"
#define WR_ARTWORK_REQUEST_BYTES 112u
#define WR_ARTWORK_REPLY_HEADER_BYTES 113u
#define WR_ARTWORK_REPLY_MAX (WR_ARTWORK_REPLY_HEADER_BYTES + XW_ARTWORK_CHUNK)
struct wr_artwork_request {
    uint64_t session;
    uint32_t request, offset;
    struct xw_media_id id;
};
struct wr_artwork_reply {
    uint64_t session;
    uint32_t request;
    int32_t result;
    struct xw_artwork_chunk chunk;
};
#ifdef __cplusplus
extern "C" {
#endif
int wr_artwork_request_encode(void *, size_t, const struct wr_artwork_request *, const uint8_t[32]);
int wr_artwork_request_decode(struct wr_artwork_request *, const void *, size_t, const uint8_t[32]);
int wr_artwork_reply_encode(void *, size_t, const struct wr_artwork_reply *, const uint8_t[32]);
int wr_artwork_reply_decode(struct wr_artwork_reply *, const void *, size_t, const uint8_t[32]);
/* All data is authenticated and bound to session + opaque song ID + offset.
 * No path, image decoder, network IO or native handle in this codec. */
#ifdef __cplusplus
}
#endif
#endif
