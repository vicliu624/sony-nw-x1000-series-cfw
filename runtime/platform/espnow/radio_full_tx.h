#ifndef XNOW_RADIO_FULL_TX_H
#define XNOW_RADIO_FULL_TX_H
#include <stdint.h>
#define XNOW_FULL_TX_MAGIC 0x3254584eu
enum xnow_full_tx_operation {XNOW_FULL_ALLOCATE=1,XNOW_FULL_SUBMIT=2,XNOW_FULL_ABORT=3,XNOW_FULL_SUBMIT_PROTECTED=4};
/* Radio-internal fixed-width control block; not yet a public/deployed ABI.
 * Packet access is permitted only between acknowledged ALLOCATE and SUBMIT/
 * ABORT. Acknowledged SUBMIT means queue acceptance, NOT a MAC/application ACK.
 * The native full transport must bound every packet write and validate wire
 * frames. This does not add encrypted-frame or DMA-completion support. */
struct xnow_full_tx_control {
    volatile uint32_t magic,request,ack,result,operation,body_bytes,packet,capacity;
    volatile uint8_t destination[6],reserved[2];
};
extern struct xnow_full_tx_control xnow_full_tx;
#endif
