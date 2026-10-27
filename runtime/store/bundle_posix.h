#ifndef HB_STORE_BUNDLE_POSIX_H
#define HB_STORE_BUNDLE_POSIX_H
#include "inventory.h"
/* Caller-owned workspace (~60KiB), never place one per recursive directory. */
struct hb_bundle {
 struct hb_inventory inventory;
 struct hb_package package;
 unsigned inventory_bytes;
 int has_inventory;
 unsigned char inventory_text[HB_INVENTORY_TEXT_BYTES];
 unsigned char manifest_sha256[32],inventory_sha256[32];
};
/* Read-only POSIX prototype: legacy two-file package, or a complete HBFILES1
 * package. Does not install, execute, follow symlinks or authenticate publishers. */
int hb_bundle_check(const char *folder,const char *id,volatile int *stop,struct hb_bundle *);
/* Conservative stage-allocation bound only; excludes receipt/rollback metadata. */
int hb_bundle_allocation_bound(const struct hb_bundle *,unsigned unit,unsigned long long *);
#endif
