idf_component_register(SRCS "main.c" "../../marble.c" INCLUDE_DIRS "../.."
 REQUIRES esp-mosaico-bsp esp_wifi esp_netif esp_event nvs_flash esp_timer)
