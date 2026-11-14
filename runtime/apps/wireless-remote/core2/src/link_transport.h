#ifndef WALKMAN_REMOTE_LINK_TRANSPORT_H
#define WALKMAN_REMOTE_LINK_TRANSPORT_H

#include <esp_now.h>
#include "../../../../platform/espnow/xnow_link.h"

namespace walkman_remote {

/* Owns one native ESP-NOW peer. Only the ordinary loop calls these methods;
 * Wi-Fi callbacks copy frames and account completions without peer mutation. */
class ControllerLink {
  public:
    ControllerLink() = default;
    ControllerLink(const ControllerLink &) = delete;
    ControllerLink &operator=(const ControllerLink &) = delete;
    using Send = esp_err_t (*)(const uint8_t *, const uint8_t *, size_t);
    using Clock = uint64_t (*)();
    esp_err_t bind(const uint8_t local[6], const uint8_t peer[6], const uint8_t authentication[32],
                   const uint8_t pmk[16], Send, Clock);
    int connect(uint64_t now);
    bool receive(const uint8_t source[6], bool broadcast, const uint8_t *, size_t, uint64_t now);
    /* 1 new key applied, 2 attempt expired, 0 ordinary progress, negative fault.
     * tx_idle covers every submitted native send, including pairing traffic. */
    int step(uint64_t now, bool tx_idle);
    esp_err_t close(bool tx_idle);
    bool ready() const;
    bool bound() const { return bound_; }
    bool negotiating() const { return bound_ && link_.candidate; }
    bool failed() const { return fault_; }
    unsigned phase() const { return link_.phase; }
    uint64_t epoch() const { return link_.active_serial; }
    void require_fresh() { needs_check_ = true; }

  private:
    static int entropy(void *, uint8_t *, size_t);
    void erase();
    xnow_link link_{};
    uint8_t peer_[6]{};
    Send send_ = nullptr;
    Clock clock_ = nullptr;
    uint64_t next_submit_ = 0;
    bool bound_ = false, closing_ = false, fault_ = false, needs_check_ = true;
};

} // namespace walkman_remote
#endif
