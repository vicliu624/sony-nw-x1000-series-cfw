#ifndef WALKMAN_REMOTE_TX_FRAME_OBSERVATION_H
#define WALKMAN_REMOTE_TX_FRAME_OBSERVATION_H

#include <stddef.h>
#include <stdint.h>

/* The ESP-IDF send callback owns this transient buffer. Observe only the fixed
 * MAC/CCMP header; never retain a pointer, payload or encryption key. */
struct wr_tx_frame_observation {
    uint64_t packet_number;
    uint16_t frame_control;
    uint8_t key_id;
    uint8_t protected_frame;
    uint8_t ccmp_present;
};

static inline int wr_tx_frame_observe(const uint8_t *frame, size_t body_bytes,
                                     struct wr_tx_frame_observation *out)
{
    if (!frame || !out || frame[0] != 0xd0 || (frame[1] & 0x87) || (frame[22] & 15))
        return 0;
    struct wr_tx_frame_observation value = {0, 0, 0, 0, 0};
    value.frame_control = (uint16_t)(frame[0] | (uint16_t)frame[1] << 8);
    value.protected_frame = (frame[1] & 0x40) != 0;
    if (value.protected_frame && body_bytes >= 8) {
        const uint8_t *iv = frame + 24;
        if (!iv[2] && (iv[3] & 0x3f) == 0x20) {
            value.key_id = iv[3] >> 6;
            value.packet_number = iv[0] | (uint64_t)iv[1] << 8;
            for (unsigned i = 0; i < 4; i++)
                value.packet_number |= (uint64_t)iv[4 + i] << (16 + i * 8);
            value.ccmp_present = value.packet_number != 0;
        }
    }
    *out = value;
    return 1;
}

#endif
