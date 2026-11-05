#ifndef XW_HOST_MANAGED_SERVICE_H
#define XW_HOST_MANAGED_SERVICE_H
#include <stdint.h>
/* Analysis host internals, hidden DSO symbols. Only a qualified original-owner
 * manager integration may supply authorization, delivery FD and generation.
 * No listener, app identity policy, inherited-FD discovery or native hook here.
 * Failure does not transfer ownership of the caller's delivery descriptor.
 */
int xw_player_host_session_offer(int delivery,uint32_t requested,uint32_t authorized,uint64_t generation);
int xw_player_host_prepare_exit(uint64_t epoch,void *context,
 int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t));
unsigned xw_player_host_service_phase(void);
/* Serialized original owner: next admissible generation, not a reservation.
 * Refuses active/draining/faulted or native-exit state; output preserved. */
int xw_player_host_next_generation(uint64_t *);
/* Owner-side resource proof only; does not grant admission, allocate a
 * generation or require this player to be the active wireless consumer. */
int xw_player_host_resources_idle(void);
/* Native continuation only: exit admission may already be closed, but a
 * resource-free stock exit must remain delegated. Retained/faulted/owned
 * resources, deferred prepare and wrong owner still refuse. Never admission. */
int xw_player_host_native_resources_idle(void);
int xw_player_host_service_stop_generation(uint64_t);
/* 1 means this generation is no longer live; 0 means still live/unknown. */
int xw_player_host_generation_retired(uint64_t);
int xw_player_host_original_exiting(void);
/* Stops admission only; preserves current channels for cooperative CLOSE/ack. */
int xw_player_host_service_quiesce(void);
/* Trusted owner-side user-switch stop: drains SDK sessions/workers, borrowing
 * the still-running Sony backend. Poll phase until STOPPED; this alone proves
 * neither external radio retirement nor RF power-off. A later offer requires a
 * strictly newer generation. A registered native-exit dependency is rejected
 * unless an explicit generation-scoped stop contract covers its retirement.
 * Native exit/fault paths cannot be rearmed here. */
int xw_player_host_service_stop(void);
/* Private native Settings delivery, not an external app authorization API.
 * Backend must be bounded/nonblocking and must not equate request acceptance
 * with RF readiness. One queued request, dispatched once on a later owner tick.
 * Result is the backend's delivery result, not a radio/on-off status snapshot. */
int xw_player_host_settings_bind(void *,int (*request)(void *,uint64_t));
/* Optional bounded job poll on the same owner loop. No thread/timer is created;
 * native-exit retirement remains the separate qualified dependency contract. */
int xw_player_host_settings_bind_backend(void *,int (*request)(void *,uint64_t),void (*poll)(void *));
int xw_player_host_settings_enqueue(void);
int xw_player_host_settings_result(uint64_t,int *);
int xw_player_host_settings_unbind(void);
/* Trusted manager supplies generation-scoped external retirement, separately
 * from native-exit epochs. Must cover the complete external ownership contract.
 * Registration alone neither stops a device nor certifies power-off. */
int xw_player_host_stop_dependency(void *,int (*poll)(void *,uint64_t));
/* Private qualified-owner registration, after service activation and before
 * native prepare. Separate manager supplies a nonblocking retirement receipt
 * poll; this does not start, control or depend on any radio implementation. */
int xw_player_host_exit_dependency(void *,int (*poll)(void *,uint64_t));
enum {XW_HOST_EXIT_FACTORY=0,XW_HOST_EXIT_HOLD=1};
/* For a separately qualified native exit callsite. HOLD is not completion:
 * native preparation must stay suppressed through pending/fault/replay states.
 * No owned SDK resources permits factory fallback. No image/owner authority is
 * created by this helper; it does not inspect raw native register arguments. */
int xw_player_host_exit_decision(uint64_t epoch,void *context,
 int (*valid)(void *,uint64_t),int (*resume)(void *,uint64_t));
/* Qualified native exit event, not a phase query. Blocks later connection
 * admission even when the factory fallback needed no SDK drain. */
void xw_player_host_note_native_exit(void);
#endif
