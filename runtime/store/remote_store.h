#ifndef HB_STORE_REMOTE_STORE_H
#define HB_STORE_REMOTE_STORE_H
#include "metadata_fetch.h"
#include "remote_list.h"
#include "job_ui.h"
enum hb_remote_stage {HB_REMOTE_IDLE,HB_REMOTE_CATALOG,HB_REMOTE_LIST,HB_REMOTE_MANIFEST,HB_REMOTE_INDEX,HB_REMOTE_PACKAGE,HB_REMOTE_FINISHED};
struct hb_remote_store_config {
 const char *catalog_url;unsigned catalog_bytes;const unsigned char *catalog_sha256;
 const char *cache,*packages,*apps,*running_id;
 const br_x509_trust_anchor *anchors;size_t anchor_count;
 unsigned timeout_ms;unsigned long long reserve;
 volatile int *stop;const struct ares_options *options;int option_mask;
};
struct hb_remote_store {
 struct hb_metadata_fetch metadata;
 struct hb_remote_catalog catalog;
 struct hb_package_download_plan plan;
 struct hb_package_job job;
 unsigned char manifest[1024],index[HB_INVENTORY_TEXT_BYTES];
 unsigned manifest_bytes,index_bytes;
 enum hb_remote_stage stage;int error,selected,begun;
};
/* Stable caller-owned workspace. Configuration, trust/stop/options and roots
 * remain alive/unchanged during run. Roots are user storage by caller policy,
 * not confined by this library. Initialize only without owned resources. */
void hb_remote_store_init(struct hb_remote_store *);
/* One browse/install journey:0 finished, -1 Back/cancel/platform stop,
 * -2 failure (error+stage identify source). Retained temp ownership remains in
 * workspace; never reinitialize to hide it. No device acquisition, DNS config
 * changes, firmware operations or automatic trust-root fallback. */
int hb_remote_store_run(struct hb_remote_store *,const struct hb_remote_store_config *,const struct hb_store_painter *,const struct hb_store_ui_io *);
/* Explicit cleanup only. Does not clear platform stop or touch installed apps. */
int hb_remote_store_discard(struct hb_remote_store *);
#endif
