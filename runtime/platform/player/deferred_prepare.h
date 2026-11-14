#ifndef XW_DEFERRED_PREPARE_H
#define XW_DEFERRED_PREPARE_H
#include "service_drain.h"
enum {
    XW_PREPARE_CHECKING = 1,
    XW_PREPARE_DRAINING,
    XW_PREPARE_CALLING,
    XW_PREPARE_DONE,
    XW_PREPARE_FAULT,
    XW_PREPARE_REVOKED_DRAINING,
    XW_PREPARE_REVOKED_DONE
};
/* Private candidate, not a native hook or a timeout/suspend veto. Fresh storage,
 * serialized qualified owner only. Context must outlive the entire operation;
 * never retain the original caller's stack output pointer. Host supplies a
 * validated native epoch/context and resumes the original prepare exactly once.
 * This object does not reserve a native pending token or keep a native root alive.
 * Once cleanup starts, loss of native continuation validity does not cancel
 * owned SDK/dependency cleanup. Revocation is sticky: retire those resources,
 * then report REVOKED_DONE without calling resume, even if validity later returns.
 * REVOKED_DONE proves cleanup, not permission to resume or admit a new session.
 */
struct xw_deferred_prepare {
    struct xw_player_service_drain *drain;
    void *context;
    uint64_t epoch;
    unsigned long owner;
    unsigned state, busy;
    int (*valid)(void *, uint64_t);
    int (*resume)(void *, uint64_t);
    void *dependency_context;
    int (*dependency)(void *, uint64_t);
};
/* Trusted manager integration only, configured before prepare starts. Optional
 * nonblocking poll after SDK drain: 0 means the separately managed dependency
 * has actually retired, BUSY waits, any other result retains the existing fault
 * behavior. No radio types, driver operations, timeout or implicit completion. */
int xw_deferred_prepare_dependency(struct xw_deferred_prepare *, void *,
                                   int (*poll)(void *, uint64_t));
int xw_deferred_prepare_begin(struct xw_deferred_prepare *, struct xw_player_service_drain *,
                              uint32_t reason, uint64_t epoch, void *context,
                              int (*valid)(void *, uint64_t), int (*resume)(void *, uint64_t));
/* BUSY never forwards original prepare. DONE never forwards it again. Lost
 * continuation validity drains owned resources to REVOKED_DONE; a cleanup
 * failure remains FAULT. Neither terminal state retries the old resume. */
int xw_deferred_prepare_step(struct xw_deferred_prepare *);
/* Attach a continuation to an already quiesced SDK drain on its qualified
 * owner, without restarting cleanup or admitting new work. A successful DONE
 * drain is eligible while independent retirement keeps the host STOPPING;
 * its separate native-epoch dependency and validity checks still execute.
 * A retained broker, open admission or failed drain is refused. Not a native hook. */
int xw_deferred_prepare_adopt(struct xw_deferred_prepare *, struct xw_player_service_drain *,
                              uint64_t epoch, void *context, int (*valid)(void *, uint64_t),
                              int (*resume)(void *, uint64_t));
/* Continue an already authorized, quiesced drain after its native request was
 * cancelled before a continuation could be attached. No native callbacks are
 * retained. A completed SDK drain still has to retire its registered dependency.
 * Caller must qualify ownership and stop ordering; this grants no admission. */
int xw_deferred_prepare_drain_only(struct xw_deferred_prepare *, struct xw_player_service_drain *,
                                   uint64_t epoch);
#endif
