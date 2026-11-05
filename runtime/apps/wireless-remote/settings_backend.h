#ifndef WR_SETTINGS_BACKEND_H
#define WR_SETTINGS_BACKEND_H
#include "supervisor_process.h"
#include "../../platform/wireless/mode.h"
/* Private reviewed-profile adapter, not an automatically installed service.
 * Bind on the original SDK owner with prequalified immutable executable/profile
 * and native RF/USB admission. STARTING is a helper launch, not RF readiness.
 * RETIRED requires a fresh prepared generation/profile before another launch;
 * no private pinned config is silently reused or rewritten here. */
enum {WR_SETTINGS_OFF=1,WR_SETTINGS_STARTING,WR_SETTINGS_STOPPING,WR_SETTINGS_RETIRED,WR_SETTINGS_FAULT};
enum wr_settings_start_stage {
 WR_START_NONE,WR_START_HOST,WR_START_MODE,WR_START_PREPARE,WR_START_PROCESS,
 WR_START_OFFER,WR_START_DEPENDENCIES,WR_START_OFFERED,WR_START_CHILD_EXIT
};
struct wr_settings_start_result {
 uint64_t serial;
 enum wr_settings_start_stage stage;
 int result;
 unsigned child_reaped;
 int child_wait_status;
};
struct wr_settings_backend {
 struct wr_supervisor_process process;
 void *context;int (*admit)(void *);
 int (*wireless_mode)(void *);
 int (*prepare)(void *,uint64_t *);
 uint64_t generation,last_request;
 unsigned long owner;unsigned phase,pending_enabled;int error;
 struct wr_settings_start_result last_start;
};
struct wr_settings_view {unsigned phase,pending;int requested_enabled,error;};
/* GUI-owner-only query, no polling or hardware effect. requested_enabled is
 * intent, never RF readiness; FAULT reports -1 (unknown). Output is unchanged
 * on error. Explicit requests enqueue a target, not a toggle. */
int wr_settings_backend_query(struct wr_settings_backend *,struct wr_settings_view *);
int wr_settings_backend_start_result(struct wr_settings_backend *,struct wr_settings_start_result *);
int wr_settings_backend_request_enabled(struct wr_settings_backend *,int enabled);
/* Read-only system-mode view: this consumer never selects/enables ESP-NOW. */
int wr_settings_backend_bind(struct wr_settings_backend *,uint64_t,void *,int (*admit)(void *),int (*wireless_mode)(void *));
int wr_settings_backend_unbind(struct wr_settings_backend *);
/* Trusted reusable-profile factory only. No start, grants or profile writes.
 * Requires normal retirement and a strictly newer player generation. */
int wr_settings_backend_renew(struct wr_settings_backend *,uint64_t);
int wr_settings_backend_prepare(struct wr_settings_backend *,int (*)(void *,uint64_t *));
/* Cleanup-only owner tick when native exit suppresses normal Settings polling. */
int wr_settings_backend_cleanup_tick(struct wr_settings_backend *);
int wr_settings_backend_request_stop(struct wr_settings_backend *);
#endif
