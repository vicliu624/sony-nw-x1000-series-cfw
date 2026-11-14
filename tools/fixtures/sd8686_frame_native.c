/* Actual native adapter -> private PC socket -> original MCU instructions.
 * This executable has no player/device paths and never opens a radio socket. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../../runtime/platform/espnow/xnow_sd8686_full.h"
#include "../../runtime/platform/espnow/xnow_frame_protocol.h"
#include "full_profile.h"
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <linux/wireless.h>

enum {
    RESET = 1,
    RADIO_COMMAND,
    INJECT,
    COMPLETE,
    INFO,
    QUEUE_FAIL,
    DEFER_COMMAND,
    PRE_MAC_RELEASE,
    CLAIM_RELEASE,
    FINISH_RELEASE
};
enum {
    FAIL_NONE,
    FAIL_AFTER,
    FAIL_DEFER,
    FAIL_PARTIAL,
    FAIL_ECHO,
    FAIL_REVOKE,
    FAIL_PERSIST,
    FAIL_DURING_RELEASE
};
enum { FILTER_SEND = 1, FILTER_COMPLETE, FILTER_POP, FILTER_ALL_SUBMITS };
static int bridge, revoked, failure, failure_filter, transport_dead;
static unsigned skip_failures, repeated_failures;
static unsigned calls, submits;
static struct xnow_sd8686_full radio;
static struct xnow_full backend;
static const uint8_t local[6] = {2, 0x11, 0x22, 0x33, 0x44, 0x55}, peer[6] = {2, 1, 2, 3, 4, 5};
static unsigned get16(const uint8_t *p) { return p[0] | (unsigned)p[1] << 8; }
static uint32_t get32(const uint8_t *p) {
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static void put16(uint8_t *p, unsigned n) {
    p[0] = (uint8_t)n;
    p[1] = (uint8_t)(n >> 8);
}
static void put32(uint8_t *p, uint32_t n) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(n >> (i * 8));
}
static void all(int write_mode, void *data, size_t n) {
    uint8_t *p = data;
    while (n) {
        ssize_t k = write_mode ? write(bridge, p, n) : read(bridge, p, n);
        if (k < 0 && errno == EINTR)
            continue;
        assert(k > 0);
        p += k;
        n -= (size_t)k;
    }
}
static unsigned control(unsigned op, unsigned arg, const void *input, unsigned n, void *output,
                        unsigned capacity) {
    uint8_t header[12];
    put32(header, op);
    put32(header + 4, n);
    put32(header + 8, arg);
    all(1, header, sizeof header);
    if (n)
        all(1, (void *)input, n);
    all(0, header, 8);
    assert(!get32(header));
    unsigned bytes = get32(header + 4);
    assert(bytes <= capacity);
    if (bytes)
        all(0, output, bytes);
    return bytes;
}
static int lease(void *unused) {
    (void)unused;
    return !revoked;
}
int ioctl(int fd, unsigned long op, ...) {
    assert(fd == 123 && op == 0x8be4);
    va_list arguments;
    va_start(arguments, op);
    struct iwreq *request = va_arg(arguments, struct iwreq *);
    va_end(arguments);
    uint8_t *p = request->u.data.pointer;
    unsigned n = request->u.data.length, action = get16(p + 8);
    uint32_t address = get32(p + 12);
    assert(n <= 1500 && get16(p) == 0x86 && get16(p + 2) == n);
    calls++;
    if (action == XNOW_FRAME_SUBMIT && get32(p + 16))
        submits++;
    if (transport_dead)
        return -1;
    int match = (failure_filter == FILTER_SEND && action == XNOW_FRAME_SUBMIT && get32(p + 16)) ||
                (failure_filter == FILTER_COMPLETE && action == XNOW_FRAME_COMPLETION) ||
                (failure_filter == FILTER_POP && action == 1 &&
                 address == xnow_full_compiled_profile.layout.rx + 12) ||
                (failure_filter == FILTER_ALL_SUBMITS && action == XNOW_FRAME_SUBMIT);
    if (match && skip_failures) {
        skip_failures--;
        match = 0;
    }
    int selected = match ? failure : FAIL_NONE;
    if (match) {
        if (repeated_failures > 1)
            repeated_failures--;
        else
            failure = FAIL_NONE;
    }
    if (selected == FAIL_DEFER) {
        control(DEFER_COMMAND, 0, p, n, 0, 0);
        return -1;
    }
    uint8_t response[1500];
    unsigned used = control(RADIO_COMMAND, 0, p, n, response, sizeof response);
    if (selected == FAIL_DURING_RELEASE) {
        control(CLAIM_RELEASE, 0, 0, 0, 0, 0);
        return -1;
    }
    if (selected == FAIL_AFTER || selected == FAIL_PERSIST) {
        if (selected == FAIL_PERSIST)
            transport_dead = 1;
        return -1;
    }
    request->u.data.length = (unsigned short)used;
    memcpy(p, response, selected == FAIL_PARTIAL ? 10 : used);
    if (selected == FAIL_ECHO)
        put32(p + 28, get32(p + 28) ^ 1u);
    if (selected == FAIL_REVOKE)
        revoked = 1;
    return 0;
}
static int raw_read(void *unused, uint32_t address, uint32_t *out) {
    (void)unused;
    uint8_t p[20] = {0};
    struct iwreq req;
    memset(&req, 0, sizeof req);
    put16(p, 0x86);
    put16(p + 2, 20);
    put32(p + 12, address);
    req.u.data.pointer = p;
    req.u.data.length = 20;
    if (ioctl(123, 0x8be4, &req) || req.u.data.length != 20 || get16(p) != 0x8086 || get16(p + 6))
        return -1;
    *out = get32(p + 16);
    return 0;
}
static int raw_write(void *unused, uint32_t address, uint32_t value) {
    (void)unused;
    uint8_t p[20] = {0};
    struct iwreq req;
    memset(&req, 0, sizeof req);
    put16(p, 0x86);
    put16(p + 2, 20);
    put16(p + 8, 1);
    put32(p + 12, address);
    put32(p + 16, value);
    req.u.data.pointer = p;
    req.u.data.length = 20;
    return ioctl(123, 0x8be4, &req) || req.u.data.length != 20 || get16(p) != 0x8086 || get16(p + 6)
               ? -1
               : 0;
}
static void open_backend(void) {
    control(RESET, 0, 0, 0, 0, 0);
    memset(&radio, 0, sizeof radio);
    memset(&backend, 0, sizeof backend);
    revoked = failure = transport_dead = 0;
    skip_failures = repeated_failures = 0;
    radio.fd = 123;
    radio.lease_valid = lease;
    struct xnow_word_io raw = {0, raw_read, raw_write}, bounded;
    assert(!xnow_full_guard_open(&radio.boundary, &raw, &xnow_full_compiled_profile, 0, lease,
                                 &bounded));
    assert(!xnow_full_open(&backend, &bounded, &xnow_full_compiled_profile.layout));
    assert(!xnow_sd8686_full_enable_spans(&radio, &backend));
    assert(!xnow_sd8686_full_enable_frames(&radio, &backend, &xnow_full_compiled_profile,
                                           XNOW_RADIO_FRAME_MARKER));
    calls = submits = 0;
}
static void information(uint32_t result[6]) {
    uint8_t p[24];
    assert(control(INFO, 0, 0, 0, p, sizeof p) == sizeof p);
    for (unsigned i = 0; i < 6; i++)
        result[i] = get32(p + i * 4);
}
static void completed(unsigned status) {
    uint8_t raw[4];
    put32(raw, 0x70302);
    control(COMPLETE, status, raw, sizeof raw, 0, 0);
}
static size_t protected_frame(uint8_t out[1560], unsigned body_bytes) {
    assert(body_bytes >= 31 && body_bytes <= 1536);
    memset(out, 0, 24 + body_bytes);
    out[0] = 0xd0;
    out[1] = 0x40;
    memcpy(out + 4, peer, 6);
    memcpy(out + 10, local, 6);
    memset(out + 16, 255, 6);
    for (unsigned i = 0; i < body_bytes; i++)
        out[24 + i] = (uint8_t)(i * 17 + 3);
    out[26] = 0;
    out[27] = 0x20;
    return 24 + body_bytes;
}
static void inject(unsigned bytes, unsigned flags) {
    uint8_t p[6 + 1536];
    memcpy(p, peer, 6);
    for (unsigned i = 0; i < bytes; i++)
        p[6 + i] = (uint8_t)(i * 11 + 7);
    if (flags & 1) {
        p[8] = 0;
        p[9] = 0x20;
    }
    control(INJECT, flags, p, 6 + bytes, 0, 0);
}
static void stop_clean(void) {
    for (unsigned i = 0;; i++) {
        assert(i < 10);
        int rc = xnow_full_stop_step(&backend);
        if (!rc)
            break;
        assert(rc == XNOW_PENDING);
        completed(0);
    }
    uint32_t state[6];
    information(state);
    assert(state[0] == 3 && !state[5]);
}
int main(void) {
    const char *fd = getenv("XNOW_TEST_BRIDGE_FD");
    assert(fd);
    bridge = atoi(fd);
    assert(bridge >= 3);
    uint8_t frame[1560], received[1560];
    uint32_t state[6];
    struct xnow_full_result result;
    size_t used;
    for (unsigned bytes = 1208; bytes <= 1536; bytes += 328) {
        open_backend();
        unsigned before = calls;
        assert(xnow_full_send_protected(&backend, local, frame, 0) == XNOW_ARGUMENT);
        size_t n = protected_frame(frame, bytes);
        assert(!xnow_full_send_protected(&backend, local, frame, n));
        unsigned sent = calls - before;
        assert(sent == (bytes > 1464 ? 2u : 1u));
        completed(0);
        before = calls;
        assert(!xnow_full_tx_result(&backend, &result) && result.stock_status == 0 &&
               result.raw_fields == 0x70302);
        unsigned done = calls - before;
        assert(done == 1);
        unsigned incoming = bytes == 1536 ? 1536 : 120;
        inject(incoming, 1);
        before = calls;
        used = 0;
        assert(!xnow_full_receive_action(&backend, local, received, sizeof received, &used));
        assert(used == 24 + incoming && received[0] == 0xd0 && received[1] == 0x40 &&
               received[26] == 0 && received[27] == 0x20);
        assert(calls - before == (incoming == 1536 ? 8u : 6u));
        printf("FRAME_NATIVE_COST body=%u TX=%u completion=%u RX=%u total=%u\n", bytes, sent, done,
               calls - before, sent + done + calls - before);
        information(state);
        assert(state[0] == 3 && state[1] == 1);
        stop_clean();
    }
    open_backend();
    inject(1536, 1);
    used = 0;
    unsigned before = calls;
    assert(!xnow_full_receive_action(&backend, local, received, sizeof received, &used) &&
           used == 1560);
    assert(calls - before == 8);
    for (unsigned i = 0; i < 1536; i++)
        assert(received[24 + i] == (i == 2 ? 0 : i == 3 ? 0x20 : (uint8_t)(i * 11 + 7)));
    stop_clean();
    /* A lost submit reply can be reconciled while original free has already
     * returned the block but the unique completion claim remains pending. */
    open_backend();
    size_t claimed_bytes = protected_frame(frame, 1208);
    failure = FAIL_DURING_RELEASE;
    failure_filter = FILTER_SEND;
    assert(xnow_full_send_protected(&backend, local, frame, claimed_bytes) == XNOW_UNCERTAIN);
    assert(backend.stopping && backend.inflight && !backend.fault && !radio.boundary.fault);
    assert(xnow_full_tx_result(&backend, &result) == XNOW_PENDING);
    control(FINISH_RELEASE, 0, 0, 0, 0, 0);
    assert(!xnow_full_tx_result(&backend, &result) && !result.stock_status &&
           result.raw_fields == 0x70302);
    stop_clean();
    /* The independent plaintext API retains its maximum binary payload and
     * too-small destination semantics under the same packet adapter. */
    open_backend();
    uint8_t payload[1470], random[4] = {1, 2, 3, 4};
    for (unsigned i = 0; i < 1470; i++)
        payload[i] = (uint8_t)(i * 19);
    assert(!xnow_full_send(&backend, peer, 2, random, payload, sizeof payload));
    completed(0);
    assert(!xnow_full_tx_result(&backend, &result));
    uint8_t wire[6 + XNOW_ESPNOW_BODY_MAX], returned[1470];
    memcpy(wire, peer, 6);
    size_t wire_bytes;
    assert(!xnow_espnow_encode_body(wire + 6, sizeof wire - 6, 2, random, payload, sizeof payload,
                                    &wire_bytes));
    control(INJECT, 0, wire, (unsigned)wire_bytes + 6, 0, 0);
    struct xnow_full_received metadata, unchanged;
    memset(&metadata, 0xa5, sizeof metadata);
    unchanged = metadata;
    memset(returned, 0xa5, sizeof returned);
    assert(xnow_full_receive(&backend, returned, sizeof returned - 1, &metadata) == XNOW_ARGUMENT);
    assert(!memcmp(&metadata, &unchanged, sizeof metadata) && returned[0] == 0xa5);
    assert(!xnow_full_receive(&backend, returned, sizeof returned, &metadata));
    assert(metadata.info.payload_bytes == 1470 && !metadata.flags &&
           !memcmp(returned, payload, sizeof payload) && !memcmp(metadata.source, peer, 6));
    stop_clean();
    open_backend();
    size_t pre_mac_bytes = protected_frame(frame, 1208);
    assert(!xnow_full_send_protected(&backend, local, frame, pre_mac_bytes));
    memset(&result, 0xa5, sizeof result);
    struct xnow_full_result old_result = result;
    assert(xnow_full_tx_result(&backend, &result) == XNOW_PENDING &&
           !memcmp(&result, &old_result, sizeof result));
    control(PRE_MAC_RELEASE, 0, 0, 0, 0, 0);
    assert(!xnow_full_tx_result(&backend, &result) &&
           result.stock_status == XNOW_FULL_TX_PRE_MAC_REJECTED && !result.raw_fields);
    stop_clean();
    for (unsigned mode = FAIL_AFTER; mode <= FAIL_ECHO; mode++) {
        open_backend();
        size_t n = protected_frame(frame, 1208);
        failure = mode;
        failure_filter = FILTER_SEND;
        assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_UNCERTAIN);
        assert(backend.stopping && !backend.fault && !radio.boundary.fault);
        information(state);
        assert(state[1] == (mode == FAIL_DEFER ? 0u : 1u));
        unsigned sent_before = submits;
        assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_PENDING &&
               submits == sent_before);
        used = 999;
        assert(xnow_full_receive_action(&backend, local, received, sizeof received, &used) ==
                   XNOW_PENDING &&
               used == 999);
        if (backend.inflight)
            completed(0);
        stop_clean();
    }
    open_backend();
    size_t n = protected_frame(frame, 1536);
    failure = FAIL_AFTER;
    failure_filter = FILTER_SEND;
    assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_UNCERTAIN &&
           backend.stopping && !backend.fault && !backend.inflight);
    information(state);
    assert(state[0] == 3 && !state[1]);
    stop_clean();
    open_backend();
    n = protected_frame(frame, 1536);
    failure = FAIL_AFTER;
    failure_filter = FILTER_SEND;
    skip_failures = 1;
    assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_UNCERTAIN &&
           backend.stopping && !backend.fault && backend.inflight);
    information(state);
    assert(state[0] == 2 && state[1] == 1);
    completed(0);
    stop_clean();
    open_backend();
    n = protected_frame(frame, 1536);
    failure = FAIL_AFTER;
    failure_filter = FILTER_ALL_SUBMITS;
    repeated_failures = 3;
    assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_UNCERTAIN &&
           backend.stopping && !backend.fault && !backend.inflight);
    information(state);
    assert(state[0] == 3 && !state[1]);
    stop_clean();
    open_backend();
    n = protected_frame(frame, 1536);
    control(QUEUE_FAIL, 1, 0, 0, 0, 0);
    assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_RADIO_REJECTED &&
           !backend.fault && !backend.inflight);
    information(state);
    assert(state[0] == 3 && !state[1]);
    stop_clean();
    open_backend();
    n = protected_frame(frame, 1208);
    assert(!xnow_full_send_protected(&backend, local, frame, n));
    completed(7);
    failure = FAIL_AFTER;
    failure_filter = FILTER_COMPLETE;
    assert(!xnow_full_tx_result(&backend, &result) && result.stock_status == 7 &&
           result.raw_fields == 0x70302);
    stop_clean();
    open_backend();
    inject(120, 1);
    inject(124, 1);
    memset(received, 0xa5, sizeof received);
    used = 999;
    assert(xnow_full_receive_action(&backend, local, received, 100, &used) == XNOW_ARGUMENT &&
           used == 999 && received[0] == 0xa5);
    information(state);
    assert(state[0] == 1 && state[3] - state[4] == 2);
    failure = FAIL_DEFER;
    failure_filter = FILTER_POP;
    assert(!xnow_full_receive_action(&backend, local, received, sizeof received, &used) &&
           used == 144);
    information(state);
    assert(state[0] == 2 && state[3] - state[4] == 1);
    assert(!xnow_full_receive_action(&backend, local, received, sizeof received, &used) &&
           used == 148);
    stop_clean();
    open_backend();
    inject(120, 1);
    inject(124, 1);
    n = protected_frame(frame, 1208);
    assert(!xnow_full_send_protected(&backend, local, frame, n));
    information(state);
    assert(!state[0] && state[1] == 1 && state[5]);
    stop_clean();
    open_backend();
    n = protected_frame(frame, 1208);
    failure = FAIL_PERSIST;
    failure_filter = FILTER_SEND;
    assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_UNCERTAIN && backend.fault &&
           radio.boundary.fault);
    information(state);
    assert(state[0] == 2 && state[1] == 1 && state[5]);
    assert(xnow_full_stop_step(&backend) == XNOW_UNCERTAIN); /* No fabricated clean retirement. */
    open_backend();
    n = protected_frame(frame, 1208);
    failure = FAIL_REVOKE;
    failure_filter = FILTER_SEND;
    assert(xnow_full_send_protected(&backend, local, frame, n) == XNOW_UNCERTAIN && backend.fault &&
           radio.boundary.fault);
    information(state);
    assert(state[0] == 2 && state[1] == 1 && state[5]);
    assert(xnow_full_stop_step(&backend) == XNOW_UNCERTAIN);
    puts("SD8686_FRAME_NATIVE_PASS: actual native/MCU commands, full payload, ticket fences, lost "
         "replies, exact RX consumption and uncertain hold.");
    return 0;
}
