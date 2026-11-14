#include "runtime/platform/espnow/xnow_link_counter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static const uint8_t root_mac[6] = {2, 0, 0, 0, 0, 1};
static const uint8_t controller_mac[6] = {2, 0, 0, 0, 0, 2};
static unsigned entropy_value = 1, legacy_commits;
static int entropy(void *context, uint8_t *out, size_t bytes)
{
    (void)context;
    memset(out, entropy_value++, bytes);
    return 0;
}
static int legacy_reserve(void *context, const uint8_t scope[32], unsigned count,
                          uint64_t *first, uint64_t *last)
{
    (void)context; (void)scope; (void)count; (void)first; (void)last;
    return -1;
}
static int legacy_load(void *context, const uint8_t scope[32], uint64_t *highest)
{
    (void)context; (void)scope;
    *highest = 18;
    return 0;
}
static int legacy_commit(void *context, const uint8_t scope[32], uint64_t highest)
{
    (void)context; (void)scope; (void)highest;
    legacy_commits++;
    return -1;
}
static void make_packet(const uint8_t key[16], uint64_t pn, uint8_t *out, size_t *bytes)
{
    uint8_t plain[XNOW_ESPNOW_ACTION_MAX], data[64], random[4] = {1, 2, 3, 4};
    size_t count;
    memset(data, 0x31, sizeof data);
    assert(!xnow_espnow_encode_action(plain, sizeof plain, root_mac, controller_mac,
                                     0, 2, random, data, sizeof data, &count));
    assert(!xnow_ccmp_espnow_seal(key, 3, pn, plain, count, out, XNOW_CCMP_FRAME_MAX, bytes));
}
static void deliver(struct xnow_link *from, struct xnow_link *to, uint64_t now)
{
    uint8_t wire[XNOW_LINK_WIRE_BYTES];
    unsigned kind;
    uint64_t ticket;
    assert(!xnow_link_take(from, wire, sizeof wire, &kind, &ticket));
    int result = xnow_link_receive(to, from->local, wire, sizeof wire, now);
    assert(result == 0 || result == XNOW_LINK_PENDING);
}
int main(void)
{
    uint8_t pmk[16], saved_lmk[16], old_wire_key[16], packet[XNOW_CCMP_FRAME_MAX], output[64];
    memset(pmk, 0x80, sizeof pmk);
    memset(saved_lmk, 0x41, sizeof saved_lmk);
    assert(!xnow_ccmp_espnow_wire_key(pmk, saved_lmk, old_wire_key));
    struct xnow_security_io legacy_io = {NULL, legacy_reserve, legacy_load, legacy_commit};
    struct xnow_security legacy;
    assert(!xnow_security_init_espnow(&legacy, &legacy_io, root_mac, controller_mac, old_wire_key, 16));
    size_t packet_bytes;
    make_packet(old_wire_key, 1, packet, &packet_bytes);
    struct xnow_wire_info info;
    assert(xnow_security_open(&legacy, packet, packet_bytes, output, sizeof output, &info) == XNOW_SECURITY_REPLAY);
    assert(legacy.rx_highest == 18 && !legacy_commits);
    puts("LEGACY_BOOT_PN1_HWM18_REPLAY");

    struct xnow_link root = {0}, controller = {0};
    uint8_t authentication[32];
    memset(authentication, 0x5a, sizeof authentication);
    assert(!xnow_link_init(&root, XNOW_LINK_ROOT, root_mac, controller_mac, authentication, NULL, entropy));
    assert(!xnow_link_init(&controller, XNOW_LINK_CONTROLLER, controller_mac, root_mac, authentication, NULL, entropy));
    assert(!xnow_link_connect(&controller, 0));
    deliver(&controller, &root, 1);
    deliver(&root, &controller, 2);
    deliver(&controller, &root, 3);
    uint64_t serial;
    uint8_t next_lmk[16], next_wire_key[16];
    assert(!xnow_link_key_pending(&root, &serial, next_lmk));
    assert(!xnow_ccmp_espnow_wire_key(pmk, next_lmk, next_wire_key));
    assert(memcmp(old_wire_key, next_wire_key, sizeof next_wire_key));
    struct xnow_link_counter counter = {0};
    struct xnow_security_io io;
    assert(!xnow_link_counter_prepare(&counter, &root, serial, pmk, &io));
    struct xnow_security current;
    assert(!xnow_security_init_espnow(&current, &io, root_mac, controller_mac, next_wire_key, 16));
    assert(!xnow_link_key_installed(&root, serial, 1, 4));
    deliver(&root, &controller, 5);
    uint64_t controller_serial;
    uint8_t controller_lmk[16];
    assert(!xnow_link_key_pending(&controller, &controller_serial, controller_lmk));
    assert(!memcmp(controller_lmk, next_lmk, sizeof next_lmk));
    assert(!xnow_link_key_installed(&controller, controller_serial, 1, 6));
    assert(!xnow_link_data_ready(&root));
    make_packet(next_wire_key, 1, packet, &packet_bytes);
    assert(!xnow_security_open(&current, packet, packet_bytes, output, sizeof output, &info));
    assert(info.payload_bytes == 64 && counter.rx_highest == 1);
    assert(!xnow_link_peer_confirmed(&root, serial) && xnow_link_data_ready(&root));
    assert(xnow_security_open(&current, packet, packet_bytes, output, sizeof output, &info) == XNOW_SECURITY_REPLAY);
    assert(counter.rx_highest == 1 && legacy.rx_highest == 18 && !legacy_commits);

    struct xnow_link_counter before = counter;
    assert(xnow_link_counter_prepare(&counter, &root, serial, pmk, &io) == XNOW_LINK_INVALID);
    assert(!memcmp(&before, &counter, sizeof counter));
    uint8_t unknown[32] = {0};
    uint64_t high = 99, first = 99, last = 99;
    assert(io.load_rx(io.context, unknown, &high) == XNOW_PN_STORAGE && high == 99);
    assert(io.reserve_tx(io.context, unknown, 16, &first, &last) == XNOW_PN_STORAGE);
    assert(first == 99 && last == 99);
    assert(io.commit_rx(io.context, counter.rx_scope, 1) == XNOW_PN_REPLAY);
    assert(!io.reserve_tx(io.context, counter.tx_scope, 16, &first, &last) && first == 1 && last == 16);
    counter.tx_highest = XNOW_PN_LIMIT - 1;
    assert(io.reserve_tx(io.context, counter.tx_scope, 2, &first, &last) == XNOW_PN_EXHAUSTED);
    xnow_link_counter_clear(&counter);
    assert(io.load_rx(io.context, before.rx_scope, &high) == XNOW_PN_STORAGE);
    puts("FRESH_LINK_PN1_ACCEPTS_AND_REPLAY_REJECTS");
    return 0;
}
