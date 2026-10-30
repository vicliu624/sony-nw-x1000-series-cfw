#ifndef XNOW_RADIO_FULL_RX_H
#define XNOW_RADIO_FULL_RX_H
#include <stdint.h>
#define XNOW_FULL_RX_MAGIC 0x3252584eu
#define XNOW_FULL_RX_SLOTS 2u
struct xnow_full_rx_slot {volatile uint32_t packet,bytes;volatile uint8_t source[6],reserved[2];};
struct xnow_full_rx_control {
    volatile uint32_t magic,head,tail,pop_ticket,dropped,result;
    struct xnow_full_rx_slot slots[XNOW_FULL_RX_SLOTS];
    /* Stop: write enabled=0, wait producer_active=0, then acknowledge/drain.
     * Never unload/reset the radio while an original TX packet is pending. */
    volatile uint32_t enabled,producer_active;
};
extern struct xnow_full_rx_control xnow_full_rx;
int xnow_radio_full_receive(const uint8_t *,void *);
void xnow_radio_rx_doorbell(uint32_t,uint32_t);
#endif
