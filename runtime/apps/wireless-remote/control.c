#include "control.h"
#include <string.h>
static uint32_t get(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static void put(uint8_t *p, uint32_t n) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(n >> (8 * i));
}
int wr_control_valid(const struct wr_control *c) {
    if (!c || !c->session || !c->request)
        return 0;
    switch (c->operation) {
    case XW_OP_PLAY:
    case XW_OP_PAUSE:
    case XW_OP_NEXT:
    case XW_OP_PREVIOUS:
        return !c->value;
    case XW_OP_STEP_VOLUME:
        return c->value == 1 || c->value == -1;
    case XW_OP_SET_VOLUME:
        return c->value >= 0 && c->value <= 255;
    case XW_OP_SET_PLAY_MODE:
        return c->value >= XW_MODE_NORMAL && c->value < XW_MODE_COUNT;
    default:
        return 0;
    }
}
static void header(uint8_t *p, const char *magic, uint64_t session, uint32_t request) {
    memset(p, 0, WR_CONTROL_BYTES);
    memcpy(p, magic, 4);
    put(p + 4, (uint32_t)session);
    put(p + 8, (uint32_t)(session >> 32));
    put(p + 12, request);
}
int wr_control_encode(void *out, size_t bytes, const struct wr_control *c, const uint8_t key[32]) {
    if (!out || !key || bytes < WR_CONTROL_BYTES || !wr_control_valid(c))
        return -1;
    uint8_t *p = out;
    header(p, "WRC1", c->session, c->request);
    put(p + 16, c->operation);
    put(p + 20, (uint32_t)c->value);
    return wr_auth_tag(p + 32, p, 32, key);
}
int wr_control_decode(struct wr_control *out, const void *data, size_t bytes,
                      const uint8_t key[32]) {
    if (!out || !data || bytes != WR_CONTROL_BYTES)
        return -1;
    const uint8_t *p = data;
    if (memcmp(p, "WRC1", 4) || get(p + 24) || get(p + 28) || wr_auth_check(p + 32, p, 32, key))
        return -1;
    struct wr_control c = {get(p + 4) | (uint64_t)get(p + 8) << 32, get(p + 12), get(p + 16),
                           (int32_t)get(p + 20)};
    if (!wr_control_valid(&c))
        return -1;
    *out = c;
    return 0;
}
int wr_receipt_encode(void *out, size_t bytes, const struct wr_control_receipt *r,
                      const uint8_t key[32]) {
    if (!out || !r || !key || bytes < WR_CONTROL_BYTES || !r->session || !r->request)
        return -1;
    uint8_t *p = out;
    header(p, "WRA1", r->session, r->request);
    put(p + 16, (uint32_t)r->result);
    return wr_auth_tag(p + 32, p, 32, key);
}
int wr_receipt_decode(struct wr_control_receipt *out, const void *data, size_t bytes,
                      const uint8_t key[32]) {
    if (!out || !data || bytes != WR_CONTROL_BYTES)
        return -1;
    const uint8_t *p = data;
    if (memcmp(p, "WRA1", 4) || get(p + 20) || get(p + 24) || get(p + 28) ||
        wr_auth_check(p + 32, p, 32, key))
        return -1;
    struct wr_control_receipt r = {get(p + 4) | (uint64_t)get(p + 8) << 32, get(p + 12),
                                   (int32_t)get(p + 16)};
    if (!r.session || !r.request)
        return -1;
    *out = r;
    return 0;
}
