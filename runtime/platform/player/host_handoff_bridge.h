#ifndef XW_HOST_HANDOFF_BRIDGE_H
#define XW_HOST_HANDOFF_BRIDGE_H
#include <stdint.h>
/* Trusted GUI glue only; native callsite/image qualification is required by
 * the dispatcher. No caller output pointer is retained. */
int xw_player_handoff_intercept(uint32_t root,uint32_t command,unsigned long owner);
void xw_player_handoff_tick(void);
/* Owner-only scheduling hint. Does not advance/authorize a transition. */
int xw_player_handoff_needs_progress(void);
/* Revoking the captured native view cancels forwarding, not owned cleanup.
 * Continue ticking until the same radio/SDK drain finishes. A cancelled
 * continuation is never rearmed merely because that view becomes valid again. */
/* Trusted paired command7 entry and post-APF-confirmation observers only. */
int xw_player_handoff_resume_begin(uint32_t root,unsigned long owner);
void xw_player_handoff_activation(uint32_t client,int native_result);
#endif
