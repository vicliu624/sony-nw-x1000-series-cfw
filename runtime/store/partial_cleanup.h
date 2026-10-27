#ifndef HB_STORE_PARTIAL_CLEANUP_H
#define HB_STORE_PARTIAL_CLEANUP_H
#include "download_record.h"
#include "package_assemble.h"
#define HB_PARTIAL_ABSENT 2
enum hb_partial_error {HB_PARTIAL_INPUT=-130,HB_PARTIAL_IO=-131,HB_PARTIAL_CANCELLED=-132};
/* Read-only full tree review, requires a verified current-plan record. Known
 * provisional files may be short/corrupt; extra/oversize/link entries reject.
 * Binds assembly in REVIEW only, never installable READY.2=tree absent. */
int hb_partial_bundle_review(struct hb_download_record *,const struct hb_package_download_plan *,struct hb_package_assembly *);
/* Explicit user choice only. Rechecks receipt/tree, reuses assembly removal,
 * syncs absent tree before dropping receipt LAST. Can retry after partial
 * deletion or post-unlink sync failure. Never touches LIVE/apps/raw storage.
 * Caller must stop writers and handle related .fetch cache files FIRST; this
 * API covers only the bundle tree/receipt, not those separate cache paths.
 * Caller owns immutable plan/stop and quiescent directory; no OS confinement. */
int hb_partial_bundle_discard(struct hb_download_record *,const struct hb_package_download_plan *,struct hb_package_assembly *);
#endif
