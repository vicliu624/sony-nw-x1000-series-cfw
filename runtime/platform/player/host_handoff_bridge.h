#ifndef XW_HOST_HANDOFF_BRIDGE_H
#define XW_HOST_HANDOFF_BRIDGE_H
#include <stdint.h>
/* Trusted GUI glue only; native callsite/image qualification is required by
 * the dispatcher. No caller output pointer is retained. */
int xw_player_handoff_intercept(uint32_t root,uint32_t command,unsigned long owner);
void xw_player_handoff_tick(void);
/* Trusted paired command7 entry and post-APF-confirmation observers only. */
int xw_player_handoff_resume_begin(uint32_t root,unsigned long owner);
void xw_player_handoff_activation(uint32_t client,int native_result);
#endif
