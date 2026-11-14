#ifndef WR_OWNER_ADMISSION_H
#define WR_OWNER_ADMISSION_H
#include "../../platform/wireless/mode_client.h"
/* Private real-owner admission. Trusted launcher supplies an already connected
 * READ-only capability and the exact lease; packet metadata grants nothing.
 * No thread, timer, radio operation or hardware-off inference is owned here. */
enum {WR_OWNER_OBSERVATION_REFRESH_MS=200,WR_OWNER_OBSERVATION_STALE_MS=1000};
enum wr_owner_retirement_phase {
 WR_OWNER_RETIREMENT_NONE,
 WR_OWNER_RETIREMENT_QUERYING,
 WR_OWNER_RETIREMENT_VERIFIED,
 WR_OWNER_RETIREMENT_FAILED
};
struct wr_owner_admission {
 struct xw_mode_client client;
 struct xw_wireless_lease expected;
 unsigned authorized,revoked,closed;
 unsigned timed,observed,rechecking;uint64_t last_poll,observed_at,query_started;
 unsigned had_data_permission;
 enum wr_owner_retirement_phase retirement;
};
int wr_owner_admission_open(struct wr_owner_admission *,int,const struct xw_wireless_lease *);
int wr_owner_admission_open_shared(struct wr_owner_admission *,int,const struct xw_wireless_lease *);
int wr_owner_admission_refresh(struct wr_owner_admission *);
int wr_owner_admission_step(struct wr_owner_admission *);
/* Single owner loop, not a timer thread. Start on a fresh connection; do not
 * mix with manual refresh/step. Refresh every200ms; a1000ms stale observation
 * or clock regression revokes DATA permission, never RF cleanup ownership. */
int wr_owner_admission_poll(struct wr_owner_admission *,uint64_t now_ms);
/* After a previously admitted synchronous operation: discard cached permission and demand
 * a new correlated reply after blocking driver work. Any preexisting reply is
 * drained first without granting data. poll() finishes the fresh observation.
 * This cannot revive a revoked/closed observer or extend a pending query's
 * normal timeout after recheck begins. No hardware ownership is acquired. */
int wr_owner_admission_recheck_begin(struct wr_owner_admission *,uint64_t now_ms);
/* One-way cleanup observation for an already-authorized owner. It revokes DATA
 * permanently, drains any old reply and requires a fresh snapshot of the same
 * retained lease. STABLE/DRAINING/FAILED ownership may permit restoring owned
 * resources; no new work, hardware-off proof or policy recovery is granted.
 * The existing one-second query bound is retained. A verified result is consumed
 * once; callers still need their independent native/owner retirement checks. */
int wr_owner_admission_retirement_begin(struct wr_owner_admission *,uint64_t now_ms);
int wr_owner_admission_retirement_poll(struct wr_owner_admission *,uint64_t now_ms);
/* Last accepted observation only, not an independent physical/instantaneous
 * authority check. Caller must refresh and honor its managed stop channel. */
int wr_owner_admission_allowed(const struct wr_owner_admission *);
/* Disposes observation only. Even return0 is never RF retirement/off proof. */
int wr_owner_admission_close(struct wr_owner_admission *);
#endif
