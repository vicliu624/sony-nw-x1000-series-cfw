idf_component_register(SRCS "main.cpp" "../../link.c" "../../status_auth.c" "../../receiver.c" "../../session_wire.c" "../../control.c" "../../../../native/sha256.c" INCLUDE_DIRS "."
    REQUIRES M5GFX esp_wifi esp_event esp_netif driver json)
idf_component_get_property(M5GFX_TARGET M5GFX COMPONENT_LIB)
target_compile_definitions(${M5GFX_TARGET} PRIVATE M5GFX_BOARD=14)
