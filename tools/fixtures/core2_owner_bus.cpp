#define main unused_core2_unit_checks
#include "core2_link.cpp"
#undef main
#include "core2_owner_bus.h"
#include "runtime/platform/espnow/xnow_wire.h"
#include "runtime/platform/espnow/xnow_ccmp.h"
#include <memory>
#include <vector>

static uint64_t controller_pn, root_highest;
static unsigned controller_messages, root_messages;
static bool confirm_sent;
static std::vector<uint8_t> app_events;
static void inject_payload(const void *payload, size_t size, bool encrypted) {
    uint8_t plain[XNOW_ESPNOW_ACTION_MAX], wire[XNOW_CCMP_FRAME_MAX], key[16],
        salt[4] = {1, 2, 3, 4};
    size_t n, bytes;
    assert(!xnow_espnow_encode_action(plain, sizeof plain, encrypted ? root_mac : broadcast,
                                      controller_mac, 0, 2, salt, payload, size, &n));
    if (encrypted) {
        const auto &peer = peers.at(address(root_mac));
        assert(peer.encrypt);
        assert(!xnow_ccmp_espnow_wire_key(pmk, peer.lmk, key));
        assert(
            !xnow_ccmp_espnow_seal(key, 3, ++controller_pn, plain, n, wire, sizeof wire, &bytes));
        bus_root_inject(wire, bytes);
    } else
        bus_root_inject(plain, n);
}
static void collect_events() {
    uint8_t bytes[2048];
    size_t count = bus_root_read(bytes, sizeof bytes);
    app_events.insert(app_events.end(), bytes, bytes + count);
    while (app_events.size() >= 16) {
        unsigned size;
        if (!std::memcmp(app_events.data(), "XNA1", 4)) {
            size = 16;
            assert(app_events[8] == 0); // Never acknowledge PENDING as success.
        } else {
            assert(!std::memcmp(app_events.data(), "XNT1", 4) ||
                   !std::memcmp(app_events.data(), "XNR1", 4));
            size = app_events[4] | unsigned(app_events[5]) << 8;
        }
        assert(size >= 16 && size <= 1502);
        if (app_events.size() < size)
            return;
        if (!std::memcmp(app_events.data(), "XNR1", 4)) {
            assert(size == 46 && !std::memcmp(app_events.data() + 32, "CONTROLLER APP", 14));
            controller_messages++;
        }
        app_events.erase(app_events.begin(), app_events.begin() + size);
    }
}
static void round(ControllerLink &c, bool confirm = true, bool flood = false) {
    now += 10;
    int progress = c.step(now, true);
    assert(progress >= 0 && progress != 2);
    if (progress == 1) {
        controller_pn = root_highest = 0;
        confirm_sent = false;
    }
    if (!outbound.empty()) {
        auto frame = outbound.front();
        outbound.pop_front();
        inject_payload(frame.data(), frame.size(), false);
    } else if (confirm && c.ready() && (!confirm_sent || flood) && bus_root_rx_empty()) {
        inject_payload("CONTROLLER APP", 14, true);
        confirm_sent = true;
    }
    uint8_t frame[XNOW_CCMP_FRAME_MAX];
    size_t bytes;
    if (bus_root_step(now, frame, sizeof frame, &bytes)) {
        uint8_t plain[XNOW_CCMP_FRAME_MAX], data[XNOW_ESPNOW_V2_MAX];
        size_t plain_bytes;
        xnow_action_info info;
        if (frame[1] & 0x40) {
            assert(c.ready());
            const auto &peer = peers.at(address(root_mac));
            uint8_t key[16];
            assert(!xnow_ccmp_espnow_wire_key(pmk, peer.lmk, key));
            assert(!xnow_ccmp_espnow_open(key, 3, &root_highest, frame, bytes, plain, sizeof plain,
                                          &plain_bytes));
            assert(!xnow_espnow_decode_action(plain, plain_bytes, data, sizeof data, &info));
            assert(info.body.payload_bytes == 8 && !std::memcmp(data, "ROOT APP", 8));
            root_messages++;
        } else {
            assert(!xnow_espnow_decode_action(frame, bytes, data, sizeof data, &info));
            assert(c.receive(root_mac, true, data, info.body.payload_bytes, now));
        }
        bus_root_complete();
    }
    collect_events();
}
static void connect_and_exchange(ControllerLink &c, unsigned token) {
    bus_root_send(token, "ROOT APP");
    unsigned before_root = root_messages, before_controller = controller_messages;
    // Root may queue an app request, but cannot publish a premature SEND ACK.
    for (int i = 0; i < 6; i++)
        round(c, false);
    assert(!bus_root_ready() && !controller_messages && !root_messages && app_events.empty());
    for (int i = 0; root_messages == before_root || controller_messages == before_controller; i++) {
        assert(i < 300);
        round(c);
    }
    assert(bus_root_ready() && c.ready());
    assert(controller_pn == 1 && root_highest >= 1);
    for (int i = 0; i < 6; i++)
        round(c);
    assert(app_events.empty());
}
static void finish_root() {
    bus_root_stop(0);
    for (unsigned i = 0; !bus_root_finished(); i++) {
        assert(i < 300);
        uint8_t frame[1560];
        size_t n;
        (void)bus_root_step(++now, frame, sizeof frame, &n);
        bus_root_complete();
    }
    bus_root_finish();
}
int main() {
    reset_native();
    std::memset(auth, 0x5a, sizeof auth);
    std::memset(pmk, 0x3b, sizeof pmk);
    uint8_t observed[6];
    bus_root_mac(observed);
    assert(!std::memcmp(observed, root_mac, 6));
    bus_root_start(auth, pmk, controller_mac);
    auto c = std::make_unique<ControllerLink>();
    bind(*c);
    assert(!c->connect(now));
    connect_and_exchange(*c, 23);
    unsigned before_flood = root_messages;
    bus_root_send(100, "ROOT APP");
    for (unsigned i = 0; i < 100 && root_messages == before_flood; i++)
        round(*c, true, true);
    assert(root_messages > before_flood); // Continuous RX cannot starve application SEND.
    for (unsigned i = 0; i < 10; i++)
        round(*c);
    unsigned installed = bus_root_installs(), sent_before = send_count;
    now += 100000;
    for (int i = 0; i < 20; i++)
        round(*c);
    assert(send_count == sent_before && bus_root_installs() == installed && c->ready());
    // Root restarts, preserving the permanent binding and controller process.
    finish_root();
    bus_root_start(auth, pmk, controller_mac);
    controller_messages = root_messages = 0;
    connect_and_exchange(*c, 24);
    // Controller restarts under the same binding; native PN starts at 1 with a NEW key.
    auto old = peers.at(address(root_mac));
    assert(c->close(true) == ESP_OK);
    c = std::make_unique<ControllerLink>();
    bind(*c);
    assert(!c->connect(++now));
    controller_messages = root_messages = 0;
    connect_and_exchange(*c, 25);
    assert(std::memcmp(old.lmk, peers.at(address(root_mac)).lmk, 16));
    // Off cannot claim retirement while a producer or native TX is still active.
    bus_root_send(26, "ROOT APP");
    uint8_t frame[1560];
    size_t bytes;
    for (unsigned i = 0; !bus_root_step(++now, frame, sizeof frame, &bytes); i++)
        assert(i < 100);
    bus_root_stop(1);
    for (int i = 0; i < 10; i++) {
        assert(!bus_root_step(++now, frame, sizeof frame, &bytes));
        assert(!bus_root_finished());
    }
    bus_root_producer_done();
    for (int i = 0; i < 10; i++) {
        assert(!bus_root_step(++now, frame, sizeof frame, &bytes));
        assert(!bus_root_finished());
    }
    bus_root_complete();
    for (unsigned i = 0; !bus_root_finished(); i++) {
        assert(i < 300);
        (void)bus_root_step(++now, frame, sizeof frame, &bytes);
    }
    bus_root_finish();
    // Stop with a validated application RX retained behind command/reply work.
    bus_root_start(auth, pmk, controller_mac);
    controller_messages = root_messages = 0;
    connect_and_exchange(*c, 27);
    bus_root_send(28, "ROOT APP");
    inject_payload("CONTROLLER APP", 14, true);
    for (unsigned i = 0; !bus_root_pending_receive(); i++) {
        assert(i < 100);
        (void)bus_root_step(++now, frame, sizeof frame, &bytes);
        bus_root_complete();
    }
    bus_root_stop(0);
    for (unsigned i = 0; !bus_root_finished(); i++) {
        assert(i < 300);
        (void)bus_root_step(++now, frame, sizeof frame, &bytes);
        assert(bus_root_receive_cleared());
        bus_root_complete();
    }
    bus_root_finish();
    assert(c->close(true) == ESP_OK);
    std::puts("CORE2_OWNER_BUS_PASS");
}
