#ifndef HB_STORE_CLEANUP_PLAN_H
#define HB_STORE_CLEANUP_PLAN_H
#include "bundle_posix.h"
#define HB_CLEANUP_RECEIPT_MAX 25360u
struct hb_cleanup_plan {
 char id[33];
 unsigned char new_identity[32],old_inventory_sha256[32];
 unsigned old_inventory_bytes;
 int old_has_inventory;
 struct hb_inventory old_files;
};
/* Hash-based identity and accidental-corruption checksum, never a signature.
 * Bundle arguments must come from successful read-only bundle verification. */
int hb_bundle_identity(const struct hb_bundle *,unsigned char out[32]);
int hb_cleanup_plan_create(const char *id,const struct hb_bundle *old_bundle,
                            const struct hb_bundle *new_bundle,struct hb_cleanup_plan *);
int hb_cleanup_plan_encode(const struct hb_cleanup_plan *,unsigned char *,unsigned capacity,unsigned *bytes);
int hb_cleanup_plan_decode(const unsigned char *,unsigned bytes,const char *expected_id,struct hb_cleanup_plan *);
int hb_cleanup_plan_matches_live(const struct hb_cleanup_plan *,const struct hb_bundle *);
int hb_cleanup_plan_old_identity(const struct hb_cleanup_plan *,unsigned char out[32]);
#endif
