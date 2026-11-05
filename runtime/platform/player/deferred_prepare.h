#ifndef XW_DEFERRED_PREPARE_H
#define XW_DEFERRED_PREPARE_H
#include "service_drain.h"
enum {XW_PREPARE_CHECKING=1,XW_PREPARE_DRAINING,XW_PREPARE_CALLING,
      XW_PREPARE_DONE,XW_PREPARE_FAULT};
/* Private candidate, not a native hook or a timeout/suspend veto. Fresh storage,
 * serialized qualified owner only. Context must outlive the entire operation;
 * never retain the original caller's stack output pointer. Host supplies a
 * validated native epoch/context and resumes the original prepare exactly once.
 * This object does not reserve a native pending token or keep a native root alive.
 */
struct xw_deferred_prepare {
 struct xw_player_service_drain *drain;
 void *context;
 uint64_t epoch;
 unsigned long owner;
 unsigned state,busy;
 int (*valid)(void *,uint64_t);
 int (*resume)(void *,uint64_t);
 void *dependency_context;
 int (*dependency)(void *,uint64_t);
};
/* Trusted manager integration only, configured before prepare starts. Optional
 * nonblocking poll after SDK drain: 0 means the separately managed dependency
 * has actually retired, BUSY waits, any other result retains the existing fault
 * behavior. No radio types, driver operations, timeout or implicit completion. */
int xw_deferred_prepare_dependency(struct xw_deferred_prepare *,void *,int (*poll)(void *,uint64_t));
int xw_deferred_prepare_begin(struct xw_deferred_prepare *,
 struct xw_player_service_drain *,uint32_t reason,uint64_t epoch,void *context,
 int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t));
/* BUSY never forwards original prepare. DONE never forwards it again. A lost
 * context or drain fault latches FAULT; uncertain resume is never retried. */
int xw_deferred_prepare_step(struct xw_deferred_prepare *);
/* Attach a continuation to an already quiesced SDK drain on its qualified
 * owner, without restarting cleanup or admitting new work. Not a native hook. */
int xw_deferred_prepare_adopt(struct xw_deferred_prepare *,struct xw_player_service_drain *,
 uint64_t epoch,void *context,int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t));
#endif
