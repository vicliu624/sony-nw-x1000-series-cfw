#ifndef WR_RADIO_BENCHMARK_H
#define WR_RADIO_BENCHMARK_H

#include <stdint.h>

#define WR_BENCH_HEADER 12u
#define WR_BENCH_SUMMARY 24u
#define WR_BENCH_TIMING (32u + 4u * WR_BENCH_SPANS)
#define WR_BENCH_FRAMES 128u
#define WR_BENCH_MAX_PAYLOAD 1400u
#define WR_BENCH_TIMEOUT_MS 20000u
#define WR_BENCH_CLOCK_MASK 0xffffffu

enum wr_bench_span {
    WR_BENCH_OBSERVED, WR_BENCH_SERVICE_TO_OWNER, WR_BENCH_PRE_SUBMIT,
    WR_BENCH_SUBMIT_SPAN, WR_BENCH_FIRST_CHECK, WR_BENCH_COMPLETION_SPAN,
    WR_BENCH_KNOWN_PENDING, WR_BENCH_FIRST_DONE, WR_BENCH_SPANS
};

static inline uint32_t wr_bench_get(const uint8_t *p) {
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static inline void wr_bench_put(uint8_t *p, uint32_t n) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(n >> (8 * i));
}

static inline int wr_bench_payload(unsigned bytes) {
    return bytes == 256 || bytes == 1024 || bytes == WR_BENCH_MAX_PAYLOAD;
}

#ifdef WR_RADIO_BENCHMARK
#include <stddef.h>
struct xnow_owner_transport;
void wr_radio_benchmark_attach(struct xnow_owner_transport *, const uint8_t peer[6], int shared);
void wr_radio_benchmark_observe_send(const uint8_t *, size_t);
#endif

#endif
