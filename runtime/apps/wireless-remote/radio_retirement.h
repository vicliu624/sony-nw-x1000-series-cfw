#ifndef WALKMAN_REMOTE_RADIO_RETIREMENT_H
#define WALKMAN_REMOTE_RADIO_RETIREMENT_H
#include "../../platform/espnow/xnow_handoff.h"
/* Application adapter for a supervisor-owned, already armed generic radio
 * handoff. Serialized same-process use; supervisor transfers exclusive access
 * to this adapter until completion. No owner start, key setup or power action. */
struct wr_radio_retirement {struct xnow_handoff *handoff;unsigned used,done,fault;int startup_failure;};
int wr_radio_retirement_init(struct wr_radio_retirement *,struct xnow_handoff *);
/* wr_worker callback contract: 0 done, XW_PLAYER_BUSY pending, otherwise fault.
 * Completion requires the actual generic SDK parser's correlated DONE + EOF,
 * followed by local descriptor close. It proves the owner's stated retirement
 * condition, not power-off: today's owner restores the original Wi-Fi stack. */
int wr_radio_retirement_poll(void *);
#endif
