#ifndef XW_PLAYER_ARTWORK_H
#define XW_PLAYER_ARTWORK_H
#include "player.h"
#define XW_ARTWORK_MAX 524288u
#define XW_ARTWORK_CHUNK 1024u
/* Private read-only thumbnail extension. No filesystem path or native handle
 * crosses the player service. Returned ID must match the requested track. */
struct xw_artwork_blob {struct xw_media_id id;uint32_t bytes;unsigned char data[XW_ARTWORK_MAX];};
struct xw_artwork_chunk {struct xw_media_id id;uint32_t total,offset,bytes;unsigned char data[XW_ARTWORK_CHUNK];};
#endif
