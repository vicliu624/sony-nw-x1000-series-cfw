#ifndef HB_STORE_DOWNLOAD_RECOVERY_H
#define HB_STORE_DOWNLOAD_RECOVERY_H
#include "payload_cache_cleanup.h"
#include "partial_cleanup.h"
struct hb_download_recovery {
 struct hb_payload_cache_review cache;
 struct hb_package_assembly bundle;
 int prepared;
};
void hb_download_recovery_init(struct hb_download_recovery *);
/* Full read-only review of BOTH scopes. A failure authorizes no cleanup. */
int hb_download_recovery_review(struct hb_download_record *,const struct hb_package_download_plan *,const char *cache,struct hb_download_recovery *);
/* Explicit user choice. Rechecks bundle before deleting cache, then clears
 * exact cache keys, bundle, and receipt LAST. Keeps intent on earlier failures.
 * Immutable plan/stop and stopped writers/quiescent roots required. */
int hb_download_recovery_discard(struct hb_download_record *,const struct hb_package_download_plan *,struct hb_download_recovery *);
#endif
