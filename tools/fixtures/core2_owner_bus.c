#define FULL_OWNER_IPC_MAIN unused_ipc_checks
#include "full_owner_ipc.c"
#include "core2_owner_bus.h"
#include "../../runtime/platform/espnow/xnow_owner_runtime.h"
#include "../../runtime/platform/espnow/xnow_owner_link.h"

static struct xnow_owner_runtime runtime;
static struct xnow_owner_gate gate;
static struct xnow_full_control control;
static struct xnow_owner_commands commands;
static struct xnow_owner_stream stream;
static struct xnow_owner_link root;
static struct xnow_endpoint_security security;
static struct xnow_full_fingerprint range;
static struct xnow_full_profile profile;
static uint8_t binding_auth[32], binding_pmk[16], binding_peer[6];
static int app_input[2], app_output[2], handoff[2];
static volatile int stop_requested;
static uint64_t current_ms;
static uint32_t copied_token;
static unsigned nonce = 100; // Independent deterministic entropy domains in this fixture.
static int storage_guard(void *context) {
    (void)context;
    return 0;
}
static int entropy(void *context, uint8_t *out, size_t bytes) {
    (void)context;
    memset(out, ++nonce, bytes);
    return 0;
}
static int now_ms(void *context, uint64_t *out) {
    (void)context;
    *out = current_ms;
    return 0;
}
static int prepare_link(void *context, struct xnow_endpoint *endpoint, const uint8_t local[6]) {
    (void)context;
    return xnow_owner_link_prepare(&root, endpoint, &security, local, binding_peer, binding_auth,
                                   binding_pmk, 0, entropy, 0, now_ms, &stop_requested);
}
static int close_link(void *context) {
    (void)context;
    assert(xnow_full_control_finished(&control));
    return xnow_owner_link_clear(&root);
}
void bus_root_start(const uint8_t auth[32], const uint8_t pmk[16], const uint8_t peer[6]) {
    assert(signal(SIGPIPE, SIG_IGN) != SIG_ERR);
    reset();
    fixture_platform_reset();
    connection = 4;
    clients = 0;
    closes = 0;
    memset(&root, 0, sizeof root);
    memset(&security, 0, sizeof security);
    stop_requested = 0;
    copied_token = 0;
    memcpy(binding_auth, auth, 32);
    memcpy(binding_pmk, pmk, 16);
    memcpy(binding_peer, peer, 6);
    assert(!pipe(app_input) && !pipe(app_output) && !pipe(handoff));
    for (unsigned i = 0; i < 2; i++) {
        nonblock(app_input[i]);
        nonblock(app_output[i]);
    }
    nonblock(handoff[0]);
    assert(!xnow_owner_gate_open(&gate, app_input[0], &stop_requested, 0, storage_guard));
    range = (struct xnow_full_fingerprint){0x8078, 4, {0}};
    profile = (struct xnow_full_profile){layout, 1, &range};
    struct xnow_full_control_options options = {
        &gate, &profile, guard, guard, xnow_owner_gate_radio_valid, random4, 8, 1, 1};
    assert(!xnow_full_control_init(&control, &options));
    assert(!xnow_owner_commands_control(&commands, &control));
    assert(!xnow_owner_stream_open(&stream, &commands, app_input[0], app_output[1]));
    uint8_t cookie[16] = {1};
    assert(!xnow_owner_runtime_init(&runtime, &control, &gate, &stream, &commands, handoff[1],
                                    cookie, 0, prepare_link, close_link));
    struct xnow_owner_transport ops;
    assert(!xnow_owner_link_transport(&root, &ops));
    assert(!xnow_owner_runtime_transport(&runtime, &ops));
}
void bus_root_mac(uint8_t out[6]) { memset(out, 2, 6); } // Mock driver supplies this MAC.
int bus_root_step(uint64_t now, uint8_t *action, size_t capacity, size_t *bytes) {
    current_ms = now;
    int rc = xnow_owner_runtime_step(&runtime);
    assert(rc == 0 || rc == XNOW_PENDING);
    if (!control.backend.inflight || control.backend.inflight == copied_token)
        return 0;
    copied_token = control.backend.inflight;
    size_t n = *at(layout.tx + 20);
    assert(capacity >= 24 + n);
    memset(action, 0, 24);
    action[0] = 0xd0;
    action[1] = *at(layout.tx + 16) == 4 ? 0x40 : 0;
    uint32_t lo = *at(layout.tx + 32), hi = *at(layout.tx + 36);
    for (unsigned i = 0; i < 4; i++)
        action[4 + i] = (uint8_t)(lo >> (8 * i));
    action[8] = (uint8_t)hi;
    action[9] = (uint8_t)(hi >> 8);
    bus_root_mac(action + 10);
    memset(action + 16, 255, 6);
    memcpy(action + 24, (uint8_t *)packet + 32, n);
    *bytes = 24 + n;
    return 1;
}
void bus_root_inject(const uint8_t *action, size_t bytes) {
    assert(bytes > 24 && bytes <= 1560);
    if (!control.endpoint_ready)
        return; // An unprepared radio cannot queue a frame.
    uint32_t tail = *at(layout.rx + 8), slot = layout.rx + 24 + (tail & 1) * 16;
    assert(*at(layout.rx + 4) == tail);
    memcpy(packet, action + 24, bytes - 24);
    *at(slot) = PACKET;
    *at(slot + 4) = (uint32_t)(bytes - 24);
    *at(slot + 8) = action[10] | (uint32_t)action[11] << 8 | (uint32_t)action[12] << 16 |
                    (uint32_t)action[13] << 24;
    unsigned flags = (action[1] & 0x40)                                   ? 1
                     : !memcmp(action + 4, "\xff\xff\xff\xff\xff\xff", 6) ? 2
                                                                          : 0;
    *at(slot + 12) = action[14] | (uint32_t)action[15] << 8 | flags << 16;
    *at(layout.rx + 4) = tail + 1;
}
void bus_root_complete(void) {
    if (control.backend.inflight)
        done(0);
}
size_t bus_root_read(void *output, size_t capacity) {
    ssize_t count = read(app_output[0], output, capacity);
    if (count < 0) {
        assert(errno == EAGAIN);
        return 0;
    }
    return (size_t)count;
}
void bus_root_send(unsigned token, const char *data) {
    uint8_t wire[XNOW_OWNER_COMMAND_MAX];
    size_t bytes = strlen(data);
    size_t n = request(wire, XNOW_OWNER_SEND, token, (unsigned)(6 + bytes));
    memcpy(wire + 16, binding_peer, 6);
    memcpy(wire + 22, data, bytes);
    assert(write(app_input[1], wire, n) == (ssize_t)n);
}
int bus_root_ready(void) {
    struct xnow_owner_transport ops;
    assert(!xnow_owner_link_transport(&root, &ops));
    return ops.ready(ops.context);
}
unsigned bus_root_installs(void) { return root.installed; }
void bus_root_stop(unsigned active) {
    stop_requested = 1;
    *at(layout.rx + 60) = active;
}
void bus_root_producer_done(void) { *at(layout.rx + 60) = 0; }
int bus_root_finished(void) { return runtime.done; }
void bus_root_finish(void) {
    assert(runtime.done && closes && connection == 4 && !clients);
    uint8_t receipt[32];
    assert(read(handoff[0], receipt, sizeof receipt) == 32);
    assert(!memcmp(receipt, "XRFDONE1", 8) && read(handoff[0], receipt, 1) == 0);
    assert(!close(app_input[0]) && !close(app_output[1]));
    close(app_input[1]);
    close(app_output[0]);
    close(handoff[0]);
}
