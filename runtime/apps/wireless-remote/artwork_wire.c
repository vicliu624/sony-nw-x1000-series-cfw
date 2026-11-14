#include "artwork_wire.h"
#include <string.h>
static uint32_t get(const uint8_t *p) {
    uint32_t n = 0;
    for (unsigned i = 0; i < 4; i++)
        n |= (uint32_t)p[i] << (8 * i);
    return n;
}
static uint64_t u64(const uint8_t *p) { return get(p) | (uint64_t)get(p + 4) << 32; }
static void put(uint8_t *p, uint32_t n) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(n >> (8 * i));
}
static void put64(uint8_t *p, uint64_t n) {
    put(p, (uint32_t)n);
    put(p + 4, (uint32_t)(n >> 32));
}
static int identity(const char *id) {
    unsigned end = 0;
    for (unsigned i = 0; i < 65; i++) {
        unsigned c = (unsigned char)id[i];
        if (!c) {
            if (!i)
                return 0;
            end = 1;
        } else if (end || c < 33 || c > 126)
            return 0;
    }
    return end;
}
int wr_artwork_request_encode(void *output, size_t capacity, const struct wr_artwork_request *r,
                              const uint8_t key[32]) {
    if (!output || capacity < 112 || !r || !r->session || !r->request ||
        r->offset >= XW_ARTWORK_MAX || !identity(r->id.value) || !key)
        return -1;
    uint8_t p[112] = {0};
    memcpy(p, "WRAQ", 4);
    put64(p + 4, r->session);
    put(p + 12, r->request);
    put(p + 16, r->offset);
    memcpy(p + 20, r->id.value, 65);
    if (wr_auth_tag(p + 96, p, 96, key))
        return -1;
    memcpy(output, p, 112);
    return 0;
}
int wr_artwork_request_decode(struct wr_artwork_request *out, const void *input, size_t bytes,
                              const uint8_t key[32]) {
    if (!out || !input || bytes != 112 || !key)
        return -1;
    const uint8_t *p = input;
    if (memcmp(p, "WRAQ", 4) || wr_auth_check(p + 96, p, 96, key))
        return -1;
    for (unsigned i = 85; i < 96; i++)
        if (p[i])
            return -1;
    struct wr_artwork_request r = {0};
    r.session = u64(p + 4);
    r.request = get(p + 12);
    r.offset = get(p + 16);
    memcpy(r.id.value, p + 20, 65);
    if (!r.session || !r.request || r.offset >= XW_ARTWORK_MAX || !identity(r.id.value))
        return -1;
    *out = r;
    return 0;
}
static int reply_valid(const struct wr_artwork_reply *r) {
    if (!r || !r->session || !r->request || r->result > 0 || r->result < XW_PLAYER_UNCERTAIN ||
        !identity(r->chunk.id.value) || r->chunk.offset >= XW_ARTWORK_MAX)
        return 0;
    if (r->result)
        return !r->chunk.total && !r->chunk.bytes;
    return r->chunk.total && r->chunk.total <= XW_ARTWORK_MAX && r->chunk.offset < r->chunk.total &&
           r->chunk.bytes && r->chunk.bytes <= XW_ARTWORK_CHUNK &&
           r->chunk.bytes == ((r->chunk.total - r->chunk.offset) > XW_ARTWORK_CHUNK
                                  ? XW_ARTWORK_CHUNK
                                  : r->chunk.total - r->chunk.offset);
}
int wr_artwork_reply_encode(void *output, size_t capacity, const struct wr_artwork_reply *r,
                            const uint8_t key[32]) {
    if (!output || !key || !reply_valid(r) ||
        capacity < WR_ARTWORK_REPLY_HEADER_BYTES + r->chunk.bytes)
        return -1;
    uint8_t *p = output;
    size_t bytes = WR_ARTWORK_REPLY_HEADER_BYTES + r->chunk.bytes;
    memcpy(p, "WRAR", 4);
    put64(p + 4, r->session);
    put(p + 12, r->request);
    put(p + 16, (uint32_t)r->result);
    memcpy(p + 20, r->chunk.id.value, 65);
    put(p + 85, r->chunk.total);
    put(p + 89, r->chunk.offset);
    put(p + 93, r->chunk.bytes);
    memcpy(p + 97, r->chunk.data, r->chunk.bytes);
    return wr_auth_tag(p + bytes - 16, p, bytes - 16, key) ? -1 : (int)bytes;
}
int wr_artwork_reply_decode(struct wr_artwork_reply *out, const void *input, size_t bytes,
                            const uint8_t key[32]) {
    if (!out || !input || !key || bytes < WR_ARTWORK_REPLY_HEADER_BYTES ||
        bytes > WR_ARTWORK_REPLY_MAX)
        return -1;
    const uint8_t *p = input;
    if (memcmp(p, "WRAR", 4) || wr_auth_check(p + bytes - 16, p, bytes - 16, key))
        return -1;
    struct wr_artwork_reply r = {0};
    r.session = u64(p + 4);
    r.request = get(p + 12);
    r.result = (int32_t)get(p + 16);
    memcpy(r.chunk.id.value, p + 20, 65);
    r.chunk.total = get(p + 85);
    r.chunk.offset = get(p + 89);
    r.chunk.bytes = get(p + 93);
    if (r.chunk.bytes > XW_ARTWORK_CHUNK ||
        bytes != WR_ARTWORK_REPLY_HEADER_BYTES + r.chunk.bytes || !reply_valid(&r))
        return -1;
    memcpy(r.chunk.data, p + 97, r.chunk.bytes);
    *out = r;
    return 0;
}
