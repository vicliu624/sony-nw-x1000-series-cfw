#ifndef HB_STORE_DOWNLOAD_RECORD_H
#define HB_STORE_DOWNLOAD_RECORD_H
#include "download_intent.h"
enum hb_download_record_state {HB_RECORD_EMPTY,HB_RECORD_READY,HB_RECORD_REVIEW};
enum hb_download_record_error {HB_RECORD_INPUT=-120,HB_RECORD_IO=-121,HB_RECORD_EXISTS=-122,HB_RECORD_SPACE=-123,HB_RECORD_CANCELLED=-124,HB_RECORD_STAGED=-125};
#define HB_RECORD_ABSENT 2
struct hb_download_record {
 struct hb_download_intent intent;unsigned char encoded[HB_DOWNLOAD_INTENT_MAX];
 char parent[512],path[512],final_path[512];unsigned bytes;
 unsigned long long parent_device,parent_inode,device,inode;
 int fd,owns,identity_known,removed,provisional;volatile int *stop;enum hb_download_record_state state;
};
/* Stable caller workspace, canonical quiescent user-storage parent. Record
 * filename .download-<id>.intent. Stop token remains alive through discard. No directory adoption/deletion by this API. */
void hb_download_record_init(struct hb_download_record *);
/* Requires .bundle-id absent; never retroactively owns an unknown tree.
 * Writes a content-addressed temporary file, fsyncs it, renames to the final
 * record, then fsyncs parent before READY. Serial/quiescent publication only.
 * Failure may retain an owned prefix; no provisional payload may start yet. */
int hb_download_record_save(struct hb_download_record *,const char *,const struct hb_package_download_plan *,unsigned long long reserve,volatile int *);
/* Read-only recognition of the exact expected temporary filename/prefix.
 * Requires bundle absent; caller checks payload cache absence too. Returns
 * REVIEW/provisional ownership for explicit discard only, never READY. */
int hb_download_record_review_temporary(struct hb_download_record *,const char *,const struct hb_package_download_plan *,volatile int *);
/* New process: complete decoding and exact current-plan match before ownership.
 * Invalid existing records stay unowned and are never auto-discarded. */
int hb_download_record_load(struct hb_download_record *,const char *,const struct hb_package_download_plan *,volatile int *);
/* Explicit caller choice; use only AFTER the dependent provisional tree
 * and related cache files have been dealt with. Owned matching inode/content only; repeat sync after unlink
 * ambiguity, never delete a replacement. Does not clear platform stop. */
/* Read-only recheck of an owned full record, including retry after a read error. */
int hb_download_record_check(struct hb_download_record *);
int hb_download_record_discard(struct hb_download_record *);
#endif
