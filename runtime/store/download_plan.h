#ifndef HB_STORE_DOWNLOAD_PLAN_H
#define HB_STORE_DOWNLOAD_PLAN_H
#include "bundle_posix.h"
struct hb_package_download_plan {
 struct hb_bundle bundle;
 unsigned char manifest[1024],identity[32];unsigned manifest_bytes,network_files,network_bytes;
 char base_url[2400];int valid;
 char asset_prefix[41];
};
struct hb_package_download_file {char path[161],url[2400],cache_key[33];unsigned bytes;unsigned char digest[32];};
/* Stable caller-owned workspace (~60KiB). Bootstrap metadata integrity/origin
 * is caller's responsibility. Deep copies manifest/index; no I/O or activation.
 * Base is absolute HTTPS ending/, without query/fragment. */
int hb_package_download_plan_init(struct hb_package_download_plan *,const char *id,const char *base_url,
 const unsigned char *manifest,unsigned manifest_bytes,const unsigned char *index,unsigned index_bytes);
/* Random-access readonly network files; app.ini/index are already owned inline.
 * Failed lookup leaves output unchanged. No progress/commit implied. */
int hb_package_download_plan_file(const struct hb_package_download_plan *,unsigned index,struct hb_package_download_file *);
#endif
