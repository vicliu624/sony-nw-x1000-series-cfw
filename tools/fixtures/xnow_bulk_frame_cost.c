/* Count the actual complete backend path, not only its data-copy callback.
 * Reuse the existing synthetic register/packet device; no physical RF. */
#define main span_fixture_main
#include "xnow_bulk_guard.c"
#undef main

static void backend_open(struct xnow_full *backend) {
    open_radio();
    struct xnow_word_io bounded, raw = {0, read_word, write_word};
    xnow_full_guard_close(&radio.boundary);
    assert(!xnow_full_guard_open(&radio.boundary, &raw, &profile, 0, lease, &bounded));
    assert(!xnow_full_open(backend, &bounded, &layout));
    assert(!xnow_sd8686_full_enable_spans(&radio, backend));
    assert(!xnow_sd8686_full_enable_bulk(&radio, &profile, BASE + 256));
    scalar_reads = scalar_writes = bulk_calls = 0;
}
static unsigned report_cost(const char *name) {
    unsigned count = scalar_reads + scalar_writes + bulk_calls;
    printf("FRAME_COST %s scalar_reads=%u scalar_writes=%u bulk=%u total=%u\n",
           name, scalar_reads, scalar_writes, bulk_calls, count);
    scalar_reads = scalar_writes = bulk_calls = 0;
    return count;
}
int main(void) {
    assert(!span_fixture_main());
    struct xnow_full backend;
    backend_open(&backend);
    const uint8_t local[6] = {2, 9, 8, 7, 6, 5}, peer[6] = {2, 1, 2, 3, 4, 5};
    uint8_t frame[24 + 1208] = {0xd0, 0x40};
    memcpy(frame + 4, peer, 6);
    memcpy(frame + 10, local, 6);
    memset(frame + 16, 0xff, 6);
    frame[27] = 0x20;
    assert(!xnow_full_send_protected(&backend, local, frame, sizeof frame));
    assert(bulk_calls == 1 && backend.inflight);
    unsigned sent = report_cost("protected-1208-byte-body");
    *cell(layout.completion + 8) = backend.inflight;
    struct xnow_full_result result;
    assert(!xnow_full_tx_result(&backend, &result));
    unsigned complete = report_cost("TX-completion");
    prepare_rx(120);
    *cell(layout.rx + 32) = 0x03020102;
    *cell(layout.rx + 36) = 0x00010504;
    size_t used = 0;
    uint8_t received[1560];
    assert(!xnow_full_receive_action(&backend, local, received, sizeof received, &used));
    assert(used == 144 && bulk_calls == 1 && received[0] == 0xd0 && received[1] == 0x40);
    unsigned request = report_cost("protected-120-byte-body-RX");
    assert(sent > 17 && request > 21);
    printf("CACHED_IMAGE_CHUNK radio_commands=%u payload_copies=2; excludes GUI RPC, "
           "empty polls, encryption and peer retries\n", sent + complete + request);
    return 0;
}
