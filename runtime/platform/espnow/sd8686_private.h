/* Internal matching-driver helpers shared by the word and packet adapters. */
#ifndef XNOW_SD8686_PRIVATE_H
#define XNOW_SD8686_PRIVATE_H
#include "xnow_sd8686_full.h"

enum {
    SD8686_HOST_BUFFER_BYTES = 2048,
    SD8686_SNAPSHOT_MARKER = 0,
    SD8686_SNAPSHOT_POOL = 1,
    SD8686_SNAPSHOT_TX = 2,
    SD8686_SNAPSHOT_RX = SD8686_SNAPSHOT_TX + 10,
    SD8686_SNAPSHOT_COMPLETION = SD8686_SNAPSHOT_RX + 16,
    SD8686_SNAPSHOT_NODES = SD8686_SNAPSHOT_COMPLETION + 6
};
int sd8686_read_vector(struct xnow_sd8686_full *, const uint32_t *, unsigned, uint32_t *);
int sd8686_snapshot(struct xnow_sd8686_full *, uint32_t[XNOW_BULK_VECTOR_FIELDS]);
int sd8686_enable_vector(struct xnow_sd8686_full *, const struct xnow_full_profile *,
                         uint32_t marker, uint32_t expected);

static inline unsigned sd8686_get16(const uint8_t *p) { return p[0] | (unsigned)p[1] << 8; }
static inline uint32_t sd8686_get32(const uint8_t *p) {
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline void sd8686_put16(uint8_t *p, unsigned value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}
static inline void sd8686_put32(uint8_t *p, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i)
        p[i] = (uint8_t)(value >> (i * 8));
}
#endif
