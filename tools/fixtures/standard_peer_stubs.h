/* Host-only IDF/FreeRTOS boundary for the actual standard-peer translation unit. */
#ifndef STANDARD_PEER_STUBS_H
#define STANDARD_PEER_STUBS_H
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define ESP_IDF_VERSION_VAL(a,b,c) ((a)*10000+(b)*100+(c))
#define ESP_IDF_VERSION ESP_IDF_VERSION_VAL(5,5,1)
#define ESP_NOW_MAX_DATA_LEN_V2 1470
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 258
#define WIFI_IF_STA 0
#define WIFI_STORAGE_RAM 0
#define WIFI_MODE_STA 0
#define WIFI_PS_NONE 0
#define WIFI_SECOND_CHAN_NONE 0
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
#define configASSERT assert
#define ESP_ERROR_CHECK(x) assert((x)==ESP_OK)
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
typedef int portMUX_TYPE,esp_err_t,wifi_second_chan_t,esp_now_send_status_t;
typedef int wifi_promiscuous_pkt_type_t;
#define WIFI_PKT_MGMT 0
#define WIFI_PROMIS_FILTER_MASK_MGMT 1
typedef struct { unsigned sig_len,rx_state; } wifi_pkt_rx_ctrl_t;
typedef struct { wifi_pkt_rx_ctrl_t rx_ctrl;uint8_t payload[1564]; } wifi_promiscuous_pkt_t;
typedef struct { unsigned filter_mask; } wifi_promiscuous_filter_t;
esp_err_t esp_wifi_set_promiscuous(bool);
esp_err_t esp_wifi_set_promiscuous_filter(const wifi_promiscuous_filter_t *);
esp_err_t esp_wifi_set_promiscuous_rx_cb(void (*)(void *,wifi_promiscuous_pkt_type_t));
typedef struct { uint8_t *src_addr,*des_addr; } esp_now_recv_info_t;
typedef struct { int unused; } esp_now_send_info_t;
typedef struct { uint8_t peer_addr[6],lmk[16],channel;int ifidx;bool encrypt; } esp_now_peer_info_t;
typedef struct { int total_num,encrypt_num; } esp_now_peer_num_t;
typedef struct { int nvs_enable; } wifi_init_config_t;
#define WIFI_INIT_CONFIG_DEFAULT() {1}
typedef struct { size_t tx_buffer_size,rx_buffer_size; } usb_serial_jtag_driver_config_t;
typedef struct MockQueue *QueueHandle_t;
QueueHandle_t xQueueCreate(unsigned,size_t);
int xQueueSend(QueueHandle_t,const void *,unsigned);
int xQueueReceive(QueueHandle_t,void *,unsigned);
esp_err_t esp_now_set_pmk(const uint8_t *);
esp_err_t esp_now_add_peer(const esp_now_peer_info_t *);
esp_err_t esp_now_del_peer(const uint8_t *);
esp_err_t esp_now_send(const uint8_t *,const uint8_t *,size_t);
esp_err_t esp_now_get_version(uint32_t *);
esp_err_t esp_now_get_peer_num(esp_now_peer_num_t *);
esp_err_t esp_wifi_get_mac(int,uint8_t *);
esp_err_t esp_wifi_get_channel(uint8_t *,wifi_second_chan_t *);
esp_err_t esp_wifi_init(const wifi_init_config_t *);
esp_err_t esp_wifi_set_storage(int);
esp_err_t esp_wifi_set_mode(int);
esp_err_t esp_wifi_set_ps(int);
esp_err_t esp_wifi_set_channel(int,int);
esp_err_t esp_wifi_start(void);
esp_err_t esp_netif_init(void);
esp_err_t esp_event_loop_create_default(void);
esp_err_t esp_now_init(void);
esp_err_t esp_now_register_recv_cb(void (*)(const esp_now_recv_info_t *,const uint8_t *,int));
esp_err_t esp_now_register_send_cb(void (*)(const esp_now_send_info_t *,esp_now_send_status_t));
esp_err_t usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t *);
int usb_serial_jtag_read_bytes(void *,size_t,unsigned);
#endif
