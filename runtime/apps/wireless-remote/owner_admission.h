#ifndef WR_OWNER_ADMISSION_H
#define WR_OWNER_ADMISSION_H
#include "../../platform/wireless/mode_client.h"
/* Private real-owner admission. Trusted launcher supplies an already connected
 * READ-only capability and the exact lease; packet metadata grants nothing.
 * No thread, timer, radio operation or hardware-off inference is owned here. */
struct wr_owner_admission {
 struct xw_mode_client client;
 struct xw_wireless_lease expected;
 unsigned authorized,revoked,closed;
 unsigned timed,observed;uint64_t last_poll,observed_at,query_started;
};
int wr_owner_admission_open(struct wr_owner_admission *,int,const struct xw_wireless_lease *);
int wr_owner_admission_refresh(struct wr_owner_admission *);
int wr_owner_admission_step(struct wr_owner_admission *);
/* Single owner loop, not a timer thread. Start on a fresh connection; do not
 * mix with manual refresh/step. Refresh every200ms; a1000ms stale observation
 * or clock regression revokes DATA permission, never RF cleanup ownership. */
int wr_owner_admission_poll(struct wr_owner_admission *,uint64_t now_ms);
/* Last accepted observation only, not an independent physical/instantaneous
 * authority check. Caller must refresh and honor its managed stop channel. */
int wr_owner_admission_allowed(const struct wr_owner_admission *);
/* Disposes observation only. Even return0 is never RF retirement/off proof. */
int wr_owner_admission_close(struct wr_owner_admission *);
#endif
