#include "radio_tx_completion.h"
__attribute__((section(".state"))) struct xnow_tx_completion_control xnow_tx_completion;
int xnow_radio_tx_ready(void){
 return !xnow_tx_completion.pending&&xnow_tx_completion.done_token==xnow_tx_completion.done_ack;
}
void xnow_radio_tx_arm(uint32_t packet,uint32_t token){
 xnow_tx_completion.token=token;
 __asm__ volatile("":::"memory");xnow_tx_completion.pending=packet;
}
void xnow_radio_tx_cancel(uint32_t packet){
 if(xnow_tx_completion.pending==packet)xnow_tx_completion.pending=0;
}
void xnow_radio_tx_observe(uint32_t packet,uint32_t status,uint32_t raw){
 struct xnow_tx_completion_control *s=&xnow_tx_completion;
 if(!packet||packet!=s->pending)return;
 s->status=status;s->raw_fields=raw;
}
void xnow_radio_tx_released(uint32_t packet){
 struct xnow_tx_completion_control *s=&xnow_tx_completion;
 if(!packet||packet!=s->pending)return;
 __asm__ volatile("":::"memory");s->done_token=s->token;
 __asm__ volatile("":::"memory");s->pending=0;
}

