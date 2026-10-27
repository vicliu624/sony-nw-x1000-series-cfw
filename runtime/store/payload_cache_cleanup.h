#ifndef HB_STORE_PAYLOAD_CACHE_CLEANUP_H
#define HB_STORE_PAYLOAD_CACHE_CLEANUP_H
#include "download_record.h"
#define HB_PAYLOAD_CACHE_FILES 128u
struct hb_payload_cache_entry {
 char key[33];unsigned expected;
 unsigned long long device,inode,bytes;
 int present,removed;
};
struct hb_payload_cache_review {
 char parent[512];unsigned long long device,inode;
 unsigned char identity[32];unsigned count,present;
 struct hb_payload_cache_entry files[HB_PAYLOAD_CACHE_FILES];
 int valid,complete;
};
enum hb_payload_cache_error {HB_CACHE_INPUT=-140,HB_CACHE_IO=-141,HB_CACHE_CANCELLED=-142};
/* Read-only exact-key review from a verified current-plan intent. Unknown cache
 * names are unrelated and untouched. Only regular single-link files within
 * declared sizes qualify. Caller stops writers and keeps directories quiescent. */
/* Read-only pre-publication guard: known keys must be absent. No adoption. */
int hb_payload_cache_unclaimed_absent(const struct hb_package_download_plan *,const char *cache);
int hb_payload_cache_review(struct hb_download_record *,const struct hb_package_download_plan *,const char *cache,struct hb_payload_cache_review *);
/* Explicit user choice; checks every snapshot before first unlink, refuses
 * new/replaced/resized target files, tracks removal for retries, then fsyncs.
 * Does not remove the bundle or receipt. Never clear receipt before complete. */
/* Read-only absence check after a completed cleanup, usable while the receipt
 * unlink is awaiting a directory-sync retry. Does not authorize deletion. */
int hb_payload_cache_absent(const struct hb_package_download_plan *,const struct hb_payload_cache_review *);
int hb_payload_cache_discard(struct hb_download_record *,const struct hb_package_download_plan *,struct hb_payload_cache_review *);
#endif
