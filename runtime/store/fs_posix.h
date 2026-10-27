#ifndef HB_STORE_FS_POSIX_H
#define HB_STORE_FS_POSIX_H
#include "transaction.h"
/* Experimental POSIX adapter. Not linked into a device candidate. Current
 * package profile is exactly app.ini + app; extra entries are rejected.
 * root must be the existing HOMEBREW/apps directory, with canonical paths.
 * This is file-operation confinement by contract, not an OS sandbox. */
struct hb_store_fs {
 char root[512],source[512],id[33],slots[3][512],receipt[512];
 int lock_fd,uncertain,receipt_reset_requested;
 volatile int *stop;
};
int hb_store_fs_init(struct hb_store_fs *,const char *root,const char *source,volatile int *stop);
int hb_store_fs_apply(struct hb_store_fs *,const char *id,unsigned long long reserve_bytes);
int hb_store_fs_recover(struct hb_store_fs *,const char *id);
/* Explicit user choice, never an automatic fallback: keep the validated LIVE
 * version and discard its validated old backup after resetting a malformed
 * receipt. Requires both complete copies and no staging directory. */
int hb_store_fs_keep_current(struct hb_store_fs *,const char *id);
#endif
