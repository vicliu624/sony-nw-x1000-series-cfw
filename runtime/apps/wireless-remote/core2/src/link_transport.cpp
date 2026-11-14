#include "link_transport.h"
#include <esp_random.h>
#include <cstring>

namespace walkman_remote {
static const uint8_t broadcast_address[6] = {255, 255, 255, 255, 255, 255};
static void wipe(void *buffer, size_t bytes) {
    volatile uint8_t *p = static_cast<volatile uint8_t *>(buffer);
    while (bytes--)
        *p++ = 0;
}
int ControllerLink::entropy(void *, uint8_t *out, size_t bytes) {
    esp_fill_random(out, bytes);
    return 0;
}
void ControllerLink::erase() {
    xnow_link_stop(&link_);
    wipe(&link_, sizeof link_);
    wipe(peer_, sizeof peer_);
    send_ = nullptr;
    clock_ = nullptr;
    bound_ = closing_ = false;
    needs_check_ = true;
    next_submit_ = 0;
}
esp_err_t ControllerLink::bind(const uint8_t local[6], const uint8_t peer[6],
                               const uint8_t authentication[32], const uint8_t pmk[16], Send send,
                               Clock clock) {
    if (bound_ || closing_ || fault_ || !pmk || !send || !clock)
        return ESP_ERR_INVALID_STATE;
    if (xnow_link_init(&link_, XNOW_LINK_CONTROLLER, local, peer, authentication, nullptr, entropy))
        return ESP_ERR_INVALID_ARG;
    esp_now_peer_info_t entry{};
    if (!esp_now_is_peer_exist(broadcast_address)) {
        std::memcpy(entry.peer_addr, broadcast_address, 6);
        entry.ifidx = WIFI_IF_STA;
        esp_err_t result = esp_now_add_peer(&entry);
        if (result != ESP_OK) {
            erase();
            return result;
        }
    }
    std::memset(&entry, 0, sizeof entry);
    std::memcpy(entry.peer_addr, peer, 6);
    entry.ifidx = WIFI_IF_STA;
    /* Bootstrap is authenticated broadcast. No static-key encrypted frame is
     * emitted after reboot; encryption starts only with a negotiated key. */
    esp_err_t result = esp_now_set_pmk(pmk);
    if (result == ESP_OK)
        result = esp_now_add_peer(&entry);
    if (result != ESP_OK) {
        erase();
        return result;
    }
    std::memcpy(peer_, peer, 6);
    send_ = send;
    clock_ = clock;
    bound_ = true;
    return ESP_OK;
}
int ControllerLink::connect(uint64_t now) {
    if (!bound_ || closing_ || fault_)
        return XNOW_LINK_REVOKED;
    needs_check_ = true;
    return xnow_link_connect(&link_, now);
}
bool ControllerLink::receive(const uint8_t source[6], bool broadcast, const uint8_t *data,
                             size_t bytes, uint64_t now) {
    if (!data || bytes < 4 || std::memcmp(data, "XNL1", 4))
        return false;
    if (!bound_ || closing_ || fault_ || !broadcast)
        return true;
    int result = xnow_link_receive(&link_, source, data, bytes, now);
    if (result == XNOW_LINK_ENTROPY) {
        fault_ = true;
        xnow_link_stop(&link_);
    }
    if (result >= 0 && link_.candidate)
        needs_check_ = true;
    return true;
}
bool ControllerLink::ready() const {
    return bound_ && !closing_ && !fault_ && !needs_check_ && !link_.candidate &&
           xnow_link_data_ready(&link_);
}
esp_err_t ControllerLink::close(bool tx_idle) {
    if (!bound_)
        return ESP_OK;
    closing_ = true;
    xnow_link_stop(&link_);
    if (!tx_idle)
        return ESP_ERR_ESPNOW_INTERNAL;
    esp_err_t result = esp_now_del_peer(peer_);
    if (result != ESP_OK) {
        fault_ = true;
        return result;
    }
    erase();
    return ESP_OK;
}
int ControllerLink::step(uint64_t now, bool tx_idle) {
    if (closing_) {
        if (!tx_idle)
            return 0;
        return close(true) == ESP_OK ? 0 : -1;
    }
    if (!bound_)
        return 0;
    if (fault_)
        return -1;
    int result = xnow_link_tick(&link_, now);
    if (result < 0) {
        fault_ = true;
        return -1;
    }
    if (result == XNOW_LINK_EXPIRED) {
        needs_check_ = true;
        return 2;
    }
    uint64_t serial;
    uint8_t key[16];
    result = xnow_link_key_pending(&link_, &serial, key);
    if (!result) {
        if (!tx_idle) {
            wipe(key, sizeof key);
            return 0;
        }
        esp_now_peer_info_t entry{};
        std::memcpy(entry.peer_addr, peer_, 6);
        std::memcpy(entry.lmk, key, 16);
        entry.ifidx = WIFI_IF_STA;
        entry.encrypt = true;
        /* A real old-peer boundary is required. A duplicate Ready never reaches
         * this branch, so it cannot reset native counters under the same key. */
        esp_err_t changed = esp_now_del_peer(peer_);
        if (changed == ESP_OK)
            changed = esp_now_add_peer(&entry);
        wipe(key, sizeof key);
        wipe(&entry, sizeof entry);
        int applied = xnow_link_key_installed(&link_, serial, changed == ESP_OK, clock_());
        if (changed != ESP_OK || applied != XNOW_LINK_OK) {
            fault_ = true;
            return -1;
        }
        needs_check_ = false;
        return 1;
    }
    if (result != XNOW_LINK_IGNORED) {
        fault_ = true;
        return -1;
    }
    if (!tx_idle || now < next_submit_)
        return 0;
    uint8_t wire[XNOW_LINK_WIRE_BYTES];
    unsigned kind;
    uint64_t ticket;
    result = xnow_link_take(&link_, wire, sizeof wire, &kind, &ticket);
    if (result == XNOW_LINK_IGNORED)
        return 0;
    if (result) {
        fault_ = true;
        return -1;
    }
    esp_err_t sent = send_(broadcast_address, wire, sizeof wire);
    wipe(wire, sizeof wire);
    if (sent == ESP_OK)
        return 0;
    if (sent == ESP_ERR_ESPNOW_NO_MEM) {
        (void)xnow_link_resubmit(&link_, ticket);
        next_submit_ = now + 50;
        return 0;
    }
    fault_ = true;
    xnow_link_stop(&link_);
    return -1;
}
} // namespace walkman_remote
