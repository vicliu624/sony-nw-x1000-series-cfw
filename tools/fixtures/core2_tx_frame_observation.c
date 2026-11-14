#include "runtime/apps/wireless-remote/core2/src/tx_frame_observation.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    uint8_t frame[32] = {0};
    frame[0] = 0xd0;
    frame[1] = 0x40;
    frame[27] = 0xe0;
    const uint64_t cases[] = {1, 5, 17, 18, 255, 256, 65536, 0x123456789abcULL, 0xffffffffffffULL};
    for (unsigned i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        uint64_t number = cases[i];
        frame[24] = (uint8_t)number;
        frame[25] = (uint8_t)(number >> 8);
        for (unsigned j = 0; j < 4; j++) frame[28 + j] = (uint8_t)(number >> (16 + 8 * j));
        struct wr_tx_frame_observation observed;
        assert(wr_tx_frame_observe(frame, 8, &observed));
        assert(observed.protected_frame && observed.ccmp_present && observed.key_id == 3);
        assert(observed.packet_number == number && observed.frame_control == 0x40d0);
    }
    struct wr_tx_frame_observation observed;
    assert(wr_tx_frame_observe(frame, 7, &observed) && !observed.ccmp_present);
    uint8_t mac_only[24] = {0};
    mac_only[0] = 0xd0;
    mac_only[1] = 0x40;
    assert(wr_tx_frame_observe(mac_only, 0, &observed) && !observed.ccmp_present);
    frame[1] = 0;
    assert(wr_tx_frame_observe(frame, 8, &observed) && !observed.protected_frame);
    frame[1] = 0x48;
    assert(wr_tx_frame_observe(frame, 8, &observed) && observed.ccmp_present);
    for (unsigned i = 0; i < 3; i++) {
        uint8_t old = frame[26 + i];
        if (i == 0) frame[26] = 1;
        if (i == 1) frame[27] &= (uint8_t)~0x20;
        if (i == 2) frame[27] |= 1;
        assert(wr_tx_frame_observe(frame, 8, &observed) && !observed.ccmp_present);
        frame[26 + i] = old;
        frame[26] = 0;
        frame[27] = 0xe0;
    }
    memset(&observed, 0xa5, sizeof observed);
    struct wr_tx_frame_observation unchanged = observed;
    frame[0] = 0x08;
    assert(!wr_tx_frame_observe(frame, 8, &observed));
    assert(!memcmp(&observed, &unchanged, sizeof observed));
    assert(!wr_tx_frame_observe(NULL, 8, &observed));
    frame[0] = 0xd0;
    frame[22] = 1;
    assert(!wr_tx_frame_observe(frame, 8, &observed));
    puts("CORE2_TX_FRAME_OBSERVATION_PASS");
    return 0;
}
