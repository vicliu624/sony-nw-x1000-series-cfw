#ifndef HB_STORE_DOWNLOAD_INTENT_H
#define HB_STORE_DOWNLOAD_INTENT_H
#include "download_plan.h"
#include "cleanup_plan.h"
#define HB_DOWNLOAD_INTENT_MAX (HB_CLEANUP_RECEIPT_MAX+44u)
struct hb_download_intent {struct hb_cleanup_plan files;int valid;};
/* Download-only HBDL0001 envelope, distinct from installer pending/cleanup.
 * Declares allowed provisional content, never claims downloaded files verified.
 * Checksum detects accidental corruption, not publisher identity/authentication.
 * Plan must be a validated immutable download_plan. No filesystem operations. */
int hb_download_intent_create(const struct hb_package_download_plan *,struct hb_download_intent *);
int hb_download_intent_encode(const struct hb_download_intent *,unsigned char *,unsigned capacity,unsigned *bytes);
int hb_download_intent_decode(const unsigned char *,unsigned bytes,const char *id,struct hb_download_intent *);
/* Exact current-plan binding includes every path/length/digest, not identity
 * alone. No cleanup is authorized merely by successfully decoding a record. */
int hb_download_intent_matches(const struct hb_download_intent *,const struct hb_package_download_plan *);
#endif
