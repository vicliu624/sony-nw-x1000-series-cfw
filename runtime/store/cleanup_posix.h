#ifndef HB_STORE_CLEANUP_POSIX_H
#define HB_STORE_CLEANUP_POSIX_H
#include "cleanup_plan.h"
#include "pending_plan.h"
/* Caller holds the store transaction lock and supplies a verified receipt.
 * root is canonical HOMEBREW/apps; only .backup-<id> may be removed. LIVE is
 * checked against the committed identity and is never modified. The caller
 * keeps the receipt until this helper and its own parent sync have succeeded. */
int hb_cleanup_can_finish(const char *root,const struct hb_cleanup_plan *,volatile int *,struct hb_bundle *workspace);
int hb_cleanup_finish(const char *root,const struct hb_cleanup_plan *,volatile int *,struct hb_bundle *workspace);
/* Uncommitted stage is disposable only with a verified, persisted pending plan.
 * Requires the original LIVE identity, or absence of LIVE/BACKUP for a first
 * install. Planned files may be incomplete; unknown/oversize/link entries block
 * deletion. Never use this API for backup cleanup. Caller holds the store lock. */
int hb_pending_can_discard(const char *root,const struct hb_pending_plan *,volatile int *,struct hb_bundle *workspace);
int hb_pending_discard(const char *root,const struct hb_pending_plan *,volatile int *,struct hb_bundle *workspace);
#endif
