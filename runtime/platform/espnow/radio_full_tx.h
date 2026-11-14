#ifndef XNOW_RADIO_FULL_TX_H
#define XNOW_RADIO_FULL_TX_H
#include <stdint.h>
#define XNOW_FULL_TX_MAGIC 0x3254584eu
enum xnow_full_tx_operation {XNOW_FULL_ALLOCATE=1,XNOW_FULL_SUBMIT=2,XNOW_FULL_ABORT=3,XNOW_FULL_SUBMIT_PROTECTED=4};
/* Private 40-byte control layout. The scalar profile retains these operation
 * IDs; FRM1 acknowledges fragments and retains packet/body_bytes until final
 * submission or cancellation. Final submission transfers packet ownership to
 * the original queue; its release/completion is separate. Protected bodies are
 * encrypted by the native security layer, not by this control block. */
struct xnow_full_tx_control {
    volatile uint32_t magic,request,ack,result,operation,body_bytes,packet,capacity;
    volatile uint8_t destination[6],reserved[2];
};
extern struct xnow_full_tx_control xnow_full_tx;
#endif
