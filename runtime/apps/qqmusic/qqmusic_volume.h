#ifndef HB_QQMUSIC_VOLUME_H
#define HB_QQMUSIC_VOLUME_H
#include "../../../sdk/include/x1000/services/volume_policy.h"
struct qq_volume {
 int directory;uint64_t device,inode,system_device,required;
 char path[2049],source[513];
};
/* Read-only observer. Existing workspace under /contents only, caller supplies
 * independently qualified source policy. Uses actual fd stats/statvfs and two
 * kernel mount snapshots; never creates directories/files or picks a fallback.
 * Fresh object initialized once, stable exclusive application workspace. */
void qq_volume_init(struct qq_volume *);
/* Last failed open step, numeric only; single-thread controller/worker scope. */
unsigned qq_volume_failure_step(void);
int qq_volume_open(struct qq_volume *,const struct qq_storage_policy *,const char *workspace,
 const struct qq_storage_plan *,uint64_t *required);
/* Reopens/observes the same logical path and compares its pinned identity.
 * Still a preflight snapshot, not a reservation or permanent write capability. */
int qq_volume_recheck(struct qq_volume *,const struct qq_storage_plan *,uint64_t *required);
int qq_volume_close(struct qq_volume *);
#endif
