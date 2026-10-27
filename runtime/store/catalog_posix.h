#ifndef HB_STORE_CATALOG_POSIX_H
#define HB_STORE_CATALOG_POSIX_H
#include "bundle_posix.h"
#define HB_STORE_CATALOG_MAX 32
struct hb_store_catalog_entry {struct hb_package package;char folder[512];unsigned char identity[32];};
struct hb_store_catalog {unsigned count,rejected;struct hb_store_catalog_entry entries[HB_STORE_CATALOG_MAX];};
/* Read-only immediate child packages, named by app ID, ordered by ID. Workspace
 * reused for each complete bundle verification. Negative result clears count.
 * At most 64 non-hidden children / 32 valid packages; never silent truncation. */
int hb_store_catalog_scan(const char *root,volatile int *stop,
 struct hb_store_catalog *,struct hb_bundle *workspace);
#endif
