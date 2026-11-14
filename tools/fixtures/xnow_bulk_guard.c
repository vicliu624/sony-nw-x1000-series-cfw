/* Actual guard and SD8686 ioctl adapter; only the device command is modeled. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../../runtime/platform/espnow/xnow_sd8686_full.h"
#include "../../runtime/native/sha256.h"
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <linux/wireless.h>

#define BASE 0xc000a190u
#define PACKET 0xc0008bd8u
static uint32_t state[475], packet[440];
static const struct xnow_full_layout layout = {BASE, BASE + 40, BASE + 104};
static struct xnow_sd8686_full radio;
static struct xnow_full_profile profile;
static struct xnow_full_fingerprint code;
static unsigned scalar_reads, scalar_writes, bulk_calls, data_scalar_writes, aborts;
static unsigned corrupt;
static int revoked;
static uint32_t *cell(uint32_t address) {
    assert(!(address & 3));
    if (address >= BASE && address < BASE + sizeof state)
        return state + (address - BASE) / 4;
    if (address >= PACKET && address < PACKET + sizeof packet)
        return packet + (address - PACKET) / 4;
    return 0;
}
static int read_word(void *unused, uint32_t address, uint32_t *value) {
    (void)unused;
    scalar_reads++;
    if (address == 0xc000d5a8u)
        *value = 0x0003076c;
    else if (address == PACKET - 4)
        *value = PACKET - 136;
    else if (address == PACKET - 136 + 8)
        *value = PACKET;
    else if (address == PACKET - 136 + 24)
        *value = 0xc0014728u;
    else {
        uint32_t *source = cell(address);
        if (!source)
            return -1;
        *value = *source;
    }
    return 0;
}
static int write_word(void *unused, uint32_t address, uint32_t value) {
    (void)unused;
    scalar_writes++;
    if (address >= PACKET && address < PACKET + sizeof packet)
        data_scalar_writes++;
    uint32_t *destination = cell(address);
    if (!destination)
        return -1;
    *destination = value;
    if (address == layout.tx + 4) {
        *cell(layout.tx + 8) = value;
        *cell(layout.tx + 12) = 0;
        unsigned operation = *cell(layout.tx + 16);
        if (operation == 1) {
            *cell(layout.tx + 24) = PACKET;
            *cell(layout.tx + 28) = 1760;
        } else {
            if (operation == 3)
                aborts++;
            *cell(layout.tx + 24) = *cell(layout.tx + 28) = 0;
        }
    }
    return 0;
}
static int lease(void *unused) {
    (void)unused;
    return !revoked;
}
static unsigned get16(const uint8_t *p) { return p[0] | ((unsigned)p[1] << 8); }
static uint32_t get32(const uint8_t *p) {
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static void put16(uint8_t *p, unsigned value) {
    p[0] = value;
    p[1] = value >> 8;
}
static void put32(uint8_t *p, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i)
        p[i] = (uint8_t)(value >> (i * 8));
}
int ioctl(int fd, unsigned long operation, ...) {
    assert(fd == 123 && operation == 0x8be4);
    va_list arguments;
    va_start(arguments, operation);
    struct iwreq *request = va_arg(arguments, struct iwreq *);
    va_end(arguments);
    uint8_t *frame = request->u.data.pointer;
    unsigned size = get16(frame + 2), action = get16(frame + 8);
    uint32_t address = get32(frame + 12);
    assert(get16(frame) == 0x86 && request->u.data.length == size);
    if (action == 0) {
        uint32_t value;
        assert(size == 20 && !read_word(0, address, &value));
        put32(frame + 16, value);
    } else {
        bulk_calls++;
        unsigned words = get16(frame + 10);
        assert((action == 0x100 || action == 0x101) && words && words <= 371 && size <= 1500);
        assert(size == 16 + 4 * words && address >= PACKET &&
               address - PACKET <= sizeof packet - 4 * words);
        unsigned copied = corrupt == 1 ? 1 : words;
        for (unsigned i = 0; i < copied; ++i) {
            if (action == 0x100)
                put32(frame + 16 + i * 4, *cell(address + i * 4));
            else
                *cell(address + i * 4) = get32(frame + 16 + i * 4);
        }
        if (corrupt == 1)
            return -1;
        if (corrupt == 11 && bulk_calls == 2)
            return -1;
        if (corrupt == 2)
            request->u.data.length -= 4;
        if (corrupt == 3)
            put16(frame + 2, size - 4);
        if (corrupt == 4)
            put16(frame + 6, 2);
        if (corrupt == 5)
            put16(frame + 8, action ^ 1);
        if (corrupt == 6)
            put16(frame + 10, words + 1);
        if (corrupt == 7)
            put32(frame + 12, address + 4);
        if (corrupt == 8)
            revoked = 1;
        if (corrupt == 9)
            (*cell(layout.rx + 8))++;
    }
    put16(frame, corrupt == 10 ? 0x8087 : 0x8086);
    return 0;
}
static void open_radio(void) {
    memset(&radio, 0, sizeof radio);
    memset(state, 0, sizeof state);
    memset(packet, 0, sizeof packet);
    revoked = corrupt = 0;
    scalar_reads = scalar_writes = bulk_calls = data_scalar_writes = aborts = 0;
    *cell(layout.tx) = 0x3254584e;
    *cell(layout.rx) = 0x3252584e;
    *cell(BASE + 256) = 0x314b4c42;
    code.address = BASE + 256;
    code.bytes = 4;
    struct hb_sha256 hash;
    hb_sha256_init(&hash);
    hb_sha256_update(&hash, (const unsigned char *)cell(code.address), 4);
    hb_sha256_final(&hash, code.sha256);
    profile.layout = layout;
    profile.count = 1;
    profile.ranges = &code;
    struct xnow_word_io raw = {0, read_word, write_word}, bounded;
    assert(!xnow_full_guard_open(&radio.boundary, &raw, &profile, 0, lease, &bounded));
    radio.fd = 123;
    radio.lease_valid = lease;
    assert(xnow_sd8686_full_enable_bulk(&radio, &profile, BASE + 260) == XNOW_IDENTITY);
    assert(!radio.boundary.raw_spans.read && !bulk_calls);
    assert(!xnow_sd8686_full_enable_bulk(&radio, &profile, BASE + 256));
    assert(xnow_sd8686_full_enable_bulk(&radio, &profile, BASE + 256) == XNOW_IDENTITY);
    scalar_reads = scalar_writes = bulk_calls = data_scalar_writes = aborts = 0;
}
static void prepare_rx(unsigned bytes) {
    *cell(layout.rx + 4) = 1;
    *cell(layout.rx + 24) = PACKET;
    *cell(layout.rx + 28) = bytes;
    for (unsigned i = 0; i < sizeof packet; ++i)
        ((uint8_t *)packet)[i] = (uint8_t)(i * 17);
}
int main(void) {
    uint8_t input[1536], output[1536];
    for (unsigned i = 0; i < sizeof input; ++i)
        input[i] = (uint8_t)(i * 17);
    const unsigned sizes[] = {15, 120, 135, 250, 1024, 1208, 1470, 1484, 1485, 1536};
    for (unsigned i = 0; i < sizeof sizes / sizeof *sizes; ++i) {
        unsigned size = sizes[i];
        open_radio();
        prepare_rx(size);
        memset(output, 0xa5, sizeof output);
        assert(!xnow_full_guard_read_span(&radio.boundary, PACKET, output, size));
        unsigned calls = (size + 1483u) / 1484u;
        assert(!memcmp(output, input, size) && bulk_calls == calls && scalar_reads == 20);
        for (unsigned tail = size; tail < sizeof output; ++tail)
            assert(output[tail] == 0xa5);
        *cell(layout.tx + 24) = PACKET;
        *cell(layout.tx + 28) = 1760;
        scalar_reads = bulk_calls = 0;
        assert(!xnow_full_guard_write_span(&radio.boundary, PACKET + 32, input, size));
        assert(!memcmp((uint8_t *)packet + 32, input, size));
        assert(bulk_calls == calls && scalar_reads == 16 && !data_scalar_writes);
        printf("BULK bytes=%u RX_commands=%u TX_commands=%u data_commands=%u\n", size, 20 + calls,
               16 + calls, calls);
    }
    for (unsigned failure = 1; failure <= 10; ++failure) {
        open_radio();
        prepare_rx(1208);
        memset(output, 0xa5, sizeof output);
        corrupt = failure;
        assert(xnow_full_guard_read_span(&radio.boundary, PACKET, output, 1208));
        for (unsigned i = 0; i < sizeof output; ++i)
            assert(output[i] == 0xa5);
        assert(bulk_calls == 1);
        if (failure == 8 || failure == 9)
            assert(radio.boundary.fault);
    }
    open_radio();
    prepare_rx(1208);
    assert(xnow_full_guard_read_span(&radio.boundary, PACKET + 4, output, 1208) && !bulk_calls);
    *cell(layout.tx + 24) = PACKET;
    *cell(layout.tx + 28) = 1760;
    assert(xnow_full_guard_write_span(&radio.boundary, PACKET + 28, input, 1208) && !bulk_calls);
    open_radio();
    prepare_rx(1536);
    memset(output, 0xa5, sizeof output);
    corrupt = 11;
    assert(xnow_full_guard_read_span(&radio.boundary, PACKET, output, 1536) && bulk_calls == 2);
    for (unsigned i = 0; i < sizeof output; i++)
        assert(output[i] == 0xa5);
    open_radio();
    struct xnow_word_io bounded = {&radio.boundary, 0, 0};
    /* Use the normal qualified callbacks installed by open, not an unguarded write. */
    struct xnow_full backend;
    struct xnow_word_io raw = {0, read_word, write_word};
    xnow_full_guard_close(&radio.boundary);
    assert(!xnow_full_guard_open(&radio.boundary, &raw, &profile, 0, lease, &bounded));
    assert(!xnow_full_open(&backend, &bounded, &layout));
    assert(!xnow_sd8686_full_enable_spans(&radio, &backend));
    assert(!xnow_sd8686_full_enable_bulk(&radio, &profile, BASE + 256));
    corrupt = 1;
    const uint8_t peer[6] = {2, 1, 2, 3, 4, 5}, random[4] = {1, 2, 3, 4};
    assert(xnow_full_send(&backend, peer, 2, random, input, 1024) == XNOW_IO);
    assert(aborts == 1 && bulk_calls == 1 && !data_scalar_writes && !*cell(layout.tx + 24));
    puts("BULK_GUARD_PASS: actual ioctl encoding, one data command, owned intervals, staged RX, "
         "malformed responses, revoked lease, changed tail and no write fallback");
    return 0;
}
