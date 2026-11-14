/* Shared radio-only single-object ownership. Never retain a borrowed RX node. */
#include "radio_packet.h"
typedef void *(*allocate_fn)(unsigned);
typedef int (*release_fn)(void *);
int xnow_radio_pool_ready(void) {
#ifdef XNOW_RADIO_BULK_COMMANDS
    return *(const volatile uint32_t *)(uintptr_t)0xc000d5a8u == 0x0003076cu;
#else
    const volatile uint16_t *pool = (const volatile uint16_t *)(uintptr_t)0xc000d5a4;
    return pool[2] == 1900 && pool[3] == 3;
#endif
}
int xnow_radio_packet_valid(uint32_t packet) {
    if (!xnow_radio_pool_ready())
        return 0;
#ifdef XNOW_RADIO_BULK_COMMANDS
    if (packet != 0xc0008bd8u && packet != 0xc0009344u && packet != 0xc0009ab0u)
        return 0;
#else
    unsigned found = 0;
    for (unsigned i = 0; i < 3; i++)
        found |= packet == 0xc0008b4cu + i * 1900u + 140u;
    if (!found)
        return 0;
#endif
    uint32_t node = *(volatile uint32_t *)(uintptr_t)(packet - 4);
    if (node != packet - 136u)
        return 0;
    volatile uint32_t *object = (volatile uint32_t *)(uintptr_t)node;
    return object[2] == packet && object[6] == 0xc0014728u;
}
int xnow_radio_packet_allocate(uint32_t *out) {
    if (!out || !xnow_radio_pool_ready())
        return -4;
    uint32_t p = (uint32_t)(uintptr_t)((allocate_fn)(uintptr_t)0xd459)(1900);
    if (!p)
        return -3;
    if (!xnow_radio_packet_valid(p))
        return -4;
    volatile uint32_t *node = (volatile uint32_t *)(uintptr_t)(p - 136);
    node[3] = 0; /* Original release traverses this link; never inherit old chains. */
    for (unsigned i = 0; i < XNOW_RADIO_PACKET_CAPACITY / 4; i++)
        ((volatile uint32_t *)(uintptr_t)p)[i] = 0;
    *out = p;
    return 0;
}
int xnow_radio_packet_release(uint32_t packet) {
    if (!xnow_radio_packet_valid(packet))
        return -4;
    return ((release_fn)(uintptr_t)0x1360)((void *)(uintptr_t)packet);
}
