#ifndef XNOW_RADIO_TX_COMPLETION_H
#define XNOW_RADIO_TX_COMPLETION_H
#include <stdint.h>
/* Experimental single outstanding send. Raw stock result, not an ACK promise.
 * Host acknowledges done_token only after reading status/raw_fields. */
struct xnow_tx_completion_control {
 volatile uint32_t pending,token,done_token,status,raw_fields,done_ack;
};
extern struct xnow_tx_completion_control xnow_tx_completion;
int xnow_radio_tx_ready(void);
void xnow_radio_tx_arm(uint32_t,uint32_t);
void xnow_radio_tx_cancel(uint32_t);
void xnow_radio_tx_observe(uint32_t,uint32_t,uint32_t);
void xnow_radio_tx_released(uint32_t);
#endif
