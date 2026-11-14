/* Radio CPU command0x86 replacement body. Not installed by the old bridge.
 * Preserve the original action1 STORE / other-action LOAD semantics, then
 * notify a separately implemented bounded doorbell after a completed STORE. */
#include <stdint.h>
extern void xnow_radio_doorbell(uint32_t, uint32_t);
#ifdef XNOW_RADIO_BULK_COMMANDS
#include "radio_packet.h"
#include "xnow_bulk_protocol.h"
/* Immutable feature marker, included in the generated image fingerprint. */
__attribute__((used)) const uint32_t xnow_radio_bulk_commands = XNOW_BULK_IMAGE_MARKER;
unsigned xnow_radio_word_io(uint8_t *body) {
    /* Original dispatch supplies an aligned header+8 body. The command size
     * lives six bytes before it and includes the original eight-byte header. */
    uint16_t *half = (uint16_t *)body;
    uint32_t *words = (uint32_t *)body;
    unsigned action = half[0];
    uint32_t address = words[1];
    if ((action & ~1u) == XNOW_BULK_GET) {
        unsigned count = half[1];
        if (count - 1u > XNOW_BULK_WORDS - 1u || half[-3] != XNOW_BULK_HEADER_BYTES + count * 4 ||
            (address & 3))
            goto invalid;
        uint32_t packet = 0xc0008bd8u;
        for (unsigned i = 0;; i++, packet += 1900u) {
            if (i == 3)
                goto invalid;
            if (address - packet <= 1760 - count * 4 && xnow_radio_packet_valid(packet))
                break;
        }
        volatile uint32_t *data = (volatile uint32_t *)(uintptr_t)address;
        volatile uint32_t *source = words + 2, *destination = data;
        if (!(action & 1)) {
            source = data;
            destination = words + 2;
        }
        do {
            *destination++ = *source++;
        } while (--count);
    } else if (action == 1) {
        uint32_t value = words[2];
        *(volatile uint32_t *)(uintptr_t)address = value;
        __asm__ volatile("" ::: "memory");
        xnow_radio_doorbell(address, value);
    } else {
        words[2] = *(volatile uint32_t *)(uintptr_t)address;
    }
    return 0;
invalid:
    /* The original response builder copies this declared length. Rejection
     * must not propagate an oversized input length into that copy. */
    half[-3] = XNOW_BULK_HEADER_BYTES;
    return 2;
}
#else
static uint32_t read32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
void xnow_radio_word_io(uint8_t *body) {
    unsigned action = body[0] | ((unsigned)body[1] << 8);
    uint32_t address = read32(body + 4);
    if (action == 1) {
        uint32_t value = read32(body + 8);
        *(volatile uint32_t *)(uintptr_t)address = value;
        __asm__ volatile("" ::: "memory");
        xnow_radio_doorbell(address, value);
    } else {
        uint32_t value = *(volatile uint32_t *)(uintptr_t)address;
        for (unsigned i = 0; i < 4; i++)
            body[8 + i] = (uint8_t)(value >> (i * 8));
    }
}
#endif
