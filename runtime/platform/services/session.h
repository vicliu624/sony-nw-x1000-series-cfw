/* Private lifecycle core. Owner-thread only; not yet a public SDK module. */
#ifndef XW_SERVICE_SESSION_H
#define XW_SERVICE_SESSION_H
#include "types.h"
#define XW_SESSION_SLOTS 4u
struct xw_session_handle {uint64_t generation,serial;};
struct xw_session_slot {struct xw_session_handle handle;struct xw_session_snapshot snapshot;};
struct xw_session_manager {uint64_t generation,serial;uint32_t supported,busy,receipt_next,accepting;struct xw_session_slot slots[XW_SESSION_SLOTS],receipts[XW_SESSION_SLOTS];};
/* Caller supplies a distinct nonzero generation after every provider restart.
 * This core cannot authenticate clients or generate cross-restart identities. */
int xw_sessions_init(struct xw_session_manager *,uint64_t generation,uint32_t supported);
/* Owner-only. Stop admission before revoking all active sessions. Does NOT
 * run provider cleanup or assert original hardware is ready for handoff. */
int xw_sessions_quiesce(struct xw_session_manager *,uint32_t reason);
/* Deny new sessions/operations while retaining channels for explicit CLOSE. */
int xw_sessions_stop_admission(struct xw_session_manager *);
/* Requires quiesced admission. OK only when every slot is empty/closed;
 * FAULT retained, PENDING otherwise. Not a hardware-restoration assertion. */
int xw_sessions_drained(struct xw_session_manager *);
/* Trusted provider must independently revalidate original resources first.
 * No old session/grant is revived; request/session counters never reset. */
int xw_sessions_resume(struct xw_session_manager *);
/* Trusted provider supplies authorized grants; this is not an authority check. */
int xw_session_open(struct xw_session_manager *,uint32_t requested,uint32_t authorized,struct xw_session_handle *);
int xw_session_read(struct xw_session_manager *,struct xw_session_handle,struct xw_session_snapshot *);
int xw_session_admit(struct xw_session_manager *,struct xw_session_handle,uint32_t capability,uint64_t *epoch);
int xw_session_revoke(struct xw_session_manager *,struct xw_session_handle,uint32_t reason);
/* Queries live closing/fault state or a retained close receipt after slot reuse.
 * At most four successful close receipts survive. STALE is not proof of release.
 * Provider restart loses receipts; caller authorization must be checked above. */
int xw_session_close_query(struct xw_session_manager *,struct xw_session_handle,struct xw_session_snapshot *);
/* Provider step executes only after admission stops. Return0 only after drain,
 * release/restoration is established;1 pending; negative means uncertain fault.
 * No lock is held. Reentry returns BUSY; callback must itself be bounded. */
int xw_session_close_step(struct xw_session_manager *,struct xw_session_handle,int (*step)(void *,struct xw_session_handle,uint32_t),void *);
#endif
