#ifndef HB_STORE_PENDING_PLAN_H
#define HB_STORE_PENDING_PLAN_H
#include "cleanup_plan.h"
#define HB_PENDING_RECEIPT_MAX (HB_CLEANUP_RECEIPT_MAX+77u)
struct hb_pending_plan {
 int old_present;
 unsigned char old_identity[32];
 struct hb_cleanup_plan incoming;
};
/* Persist and sync this intent BEFORE creating STAGE. It owns only the named
 * provisional tree. Not a publisher signature or an authorization for LIVE. */
int hb_pending_plan_create(const char *id,const struct hb_bundle *old_bundle,
                           const struct hb_bundle *new_bundle,struct hb_pending_plan *);
int hb_pending_plan_encode(const struct hb_pending_plan *,unsigned char *,unsigned,unsigned *);
int hb_pending_plan_decode(const unsigned char *,unsigned,const char *id,struct hb_pending_plan *);
#endif
