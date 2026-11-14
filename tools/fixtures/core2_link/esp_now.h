#ifndef TEST_CORE2_ESP_NOW_H
#define TEST_CORE2_ESP_NOW_H
#include <cstddef>
#include <cstdint>
typedef int esp_err_t;
enum {
    ESP_OK = 0,
    ESP_ERR_INVALID_STATE = 1,
    ESP_ERR_INVALID_ARG = 2,
    ESP_ERR_ESPNOW_INTERNAL = 3,
    ESP_ERR_ESPNOW_NO_MEM = 4,
    WIFI_IF_STA = 0
};
struct esp_now_peer_info_t {
    uint8_t peer_addr[6], lmk[16];
    unsigned channel, ifidx;
    bool encrypt;
};
bool esp_now_is_peer_exist(const uint8_t *);
esp_err_t esp_now_add_peer(const esp_now_peer_info_t *);
esp_err_t esp_now_del_peer(const uint8_t *);
esp_err_t esp_now_set_pmk(const uint8_t *);
#endif
