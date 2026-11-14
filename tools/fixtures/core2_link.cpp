/* Public native-peer API model, not ESP silicon or an over-air simulation. */
#include "runtime/apps/wireless-remote/core2/src/link_transport.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <deque>
#include <map>
using walkman_remote::ControllerLink;
using Address = std::array<uint8_t, 6>;
using Frame = std::array<uint8_t, XNOW_LINK_WIRE_BYTES>;
static const uint8_t root_mac[6] = {2, 2, 2, 2, 2, 2}, controller_mac[6] = {2, 0, 0, 0, 0, 2};
static const uint8_t broadcast[6] = {255, 255, 255, 255, 255, 255};
static uint8_t auth[32], pmk[16];
static uint64_t now = 1, install_delay;
static unsigned entropy, adds, deletes, send_count;
static esp_err_t send_result, add_result;
static std::map<Address, esp_now_peer_info_t> peers;
static std::deque<Frame> outbound;
static Address address(const uint8_t *p) {
    Address a;
    std::memcpy(a.data(), p, 6);
    return a;
}
bool esp_now_is_peer_exist(const uint8_t *p) { return peers.count(address(p)); }
esp_err_t esp_now_set_pmk(const uint8_t *p) {
    assert(!std::memcmp(p, pmk, 16));
    return ESP_OK;
}
esp_err_t esp_now_add_peer(const esp_now_peer_info_t *p) {
    if (add_result)
        return add_result;
    assert(!peers.count(address(p->peer_addr)));
    peers[address(p->peer_addr)] = *p;
    adds++;
    if (p->encrypt)
        now += install_delay;
    return ESP_OK;
}
esp_err_t esp_now_del_peer(const uint8_t *p) {
    assert(peers.count(address(p)));
    peers.erase(address(p));
    deletes++;
    return ESP_OK;
}
void esp_fill_random(void *p, size_t n) { std::memset(p, ++entropy, n); }
static int root_random(void *, uint8_t *p, size_t n) {
    esp_fill_random(p, n);
    return 0;
}
static uint64_t clock_now() { return now; }
static esp_err_t send(const uint8_t *to, const uint8_t *p, size_t n) {
    assert(!std::memcmp(to, broadcast, 6) && n == XNOW_LINK_WIRE_BYTES);
    send_count++;
    if (send_result)
        return send_result;
    Frame frame;
    std::memcpy(frame.data(), p, n);
    outbound.push_back(frame);
    return ESP_OK;
}
static void reset_native() {
    peers.clear();
    outbound.clear();
    adds = deletes = send_count = 0;
    send_result = add_result = 0;
    install_delay = 0;
    now++;
}
static void root_init(xnow_link &root) {
    root = {};
    assert(!xnow_link_init(&root, XNOW_LINK_ROOT, root_mac, controller_mac, auth, nullptr,
                           root_random));
}
static Frame take(xnow_link &link) {
    Frame f;
    unsigned kind;
    uint64_t ticket;
    assert(!xnow_link_take(&link, f.data(), f.size(), &kind, &ticket));
    return f;
}
static Frame controller_frame(ControllerLink &controller) {
    assert(controller.step(now, true) >= 0);
    assert(!outbound.empty());
    Frame frame = outbound.front();
    outbound.pop_front();
    return frame;
}
/* Reach the point where Ready was authenticated, before native key IO. */
static Frame negotiate(xnow_link &root, ControllerLink &controller) {
    Frame hello = controller_frame(controller);
    assert(hello[5] == XNOW_LINK_HELLO);
    assert(!xnow_link_receive(&root, controller_mac, hello.data(), hello.size(), now));
    Frame offer = take(root);
    assert(offer[5] == XNOW_LINK_OFFER);
    assert(controller.receive(root_mac, true, offer.data(), offer.size(), now));
    Frame confirm = controller_frame(controller);
    assert(confirm[5] == XNOW_LINK_CONFIRM);
    assert(xnow_link_receive(&root, controller_mac, confirm.data(), confirm.size(), now) ==
           XNOW_LINK_PENDING);
    uint64_t serial;
    uint8_t key[16];
    assert(!xnow_link_key_pending(&root, &serial, key));
    assert(!xnow_link_key_installed(&root, serial, 1, now));
    Frame ready = take(root);
    assert(ready[5] == XNOW_LINK_READY);
    assert(controller.receive(root_mac, true, ready.data(), ready.size(), now));
    return ready;
}
static void bind(ControllerLink &c) {
    assert(c.bind(controller_mac, root_mac, auth, pmk, send, clock_now) == ESP_OK);
}
static void basic_and_restarts() {
    reset_native();
    ControllerLink c;
    xnow_link root;
    root_init(root);
    bind(c);
    assert(peers.size() == 2 && !peers.at(address(root_mac)).encrypt && !c.ready());
    assert(!c.connect(now));
    Frame ready = negotiate(root, c);
    unsigned before = deletes;
    assert(!c.step(now, false) && deletes == before && !c.ready());
    assert(c.step(now, true) == 1 && c.ready() && deletes == before + 1);
    assert(peers.at(address(root_mac)).encrypt);
    assert(!std::memcmp(peers.at(address(root_mac)).lmk, root.active_key, 16));
    auto key = peers.at(address(root_mac));
    for (int i = 0; i < 5; i++) {
        c.receive(root_mac, true, ready.data(), ready.size(), ++now);
        assert(!c.step(now, true) && c.ready() && deletes == before + 1);
    }
    unsigned old_sends = send_count;
    now += 100000;
    assert(!c.step(now, true) && send_count == old_sends && c.ready());
    /* An authenticated root restart begins exactly one new link, no NVS/key reset. */
    xnow_link_stop(&root);
    root_init(root);
    assert(!xnow_link_announce(&root, now));
    Frame announce = take(root);
    auto corrupt = announce;
    corrupt.back() ^= 1;
    c.receive(root_mac, true, corrupt.data(), corrupt.size(), now);
    assert(c.ready());
    c.receive(root_mac, false, announce.data(), announce.size(), now);
    assert(c.ready());
    c.receive(root_mac, true, announce.data(), announce.size(), now);
    assert(!c.ready());
    ready = negotiate(root, c);
    assert(c.step(now, true) == 1 && c.ready());
    assert(std::memcmp(peers.at(address(root_mac)).lmk, key.lmk, 16));
    key = peers.at(address(root_mac));
    /* Controller process restart with the same permanent binding. */
    assert(c.close(true) == ESP_OK && peers.size() == 1);
    ControllerLink restarted;
    bind(restarted);
    assert(!restarted.connect(++now));
    ready = negotiate(root, restarted);
    assert(restarted.step(now, true) == 1 && restarted.ready());
    assert(std::memcmp(peers.at(address(root_mac)).lmk, key.lmk, 16));
    unsigned previous = deletes;
    assert(restarted.close(false) == ESP_ERR_ESPNOW_INTERNAL);
    assert(!restarted.ready() && deletes == previous);
    assert(!restarted.step(++now, false) && deletes == previous);
    assert(!restarted.step(++now, true) && deletes == previous + 1);
    assert(!restarted.bound() && peers.size() == 1);
}
static void submission_and_expiry() {
    reset_native();
    ControllerLink c;
    bind(c);
    assert(!c.connect(now));
    send_result = ESP_ERR_ESPNOW_NO_MEM;
    assert(!c.step(now, true));
    assert(send_count == 1);
    assert(!c.step(now + 1, true) && send_count == 1);
    now += 50;
    send_result = ESP_OK;
    assert(!c.step(now, true) && send_count == 2);
    assert(!outbound.empty());
    outbound.clear();
    now += 5000;
    assert(c.step(now, true) == 2 && !c.ready());
    unsigned count = send_count;
    now += 100000;
    assert(!c.step(now, true) && send_count == count); // No automatic retry window.
    assert(!c.connect(now));
    assert(!c.step(now, false) && send_count == count);
    assert(!c.step(now, true) && send_count == count + 1);
    assert(c.close(true) == ESP_OK);
}
static void install_failures() {
    reset_native();
    ControllerLink c;
    xnow_link root;
    root_init(root);
    bind(c);
    assert(!c.connect(now));
    negotiate(root, c);
    add_result = ESP_ERR_ESPNOW_INTERNAL;
    assert(c.step(now, true) < 0 && c.failed() && !c.ready());
    unsigned previous = send_count;
    now += 100000;
    assert(c.step(now, true) < 0 && send_count == previous);
    // Separate process model: an install that finishes after the deadline is sealed.
    reset_native();
    ControllerLink late;
    root_init(root);
    bind(late);
    assert(!late.connect(now));
    negotiate(root, late);
    install_delay = 5000;
    assert(late.step(now, true) < 0 && !late.ready() && late.failed());
}
int main() {
    std::memset(auth, 0x5a, sizeof auth);
    std::memset(pmk, 0x3b, sizeof pmk);
    basic_and_restarts();
    submission_and_expiry();
    install_failures();
    std::puts("CORE2_LINK_TRANSPORT_PASS");
    return 0;
}
