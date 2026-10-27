#ifndef HB_STORE_TRANSACTION_H
#define HB_STORE_TRANSACTION_H

/* Filesystem adapter contract: all slots belong to one app on user storage.
 * The adapter must exclude concurrent installs, close files before returning,
 * validate identity/content in inspect(), and never replace an occupied slot.
 * Failed rename/remove operations must leave their inputs unchanged. Unknown
 * filesystem outcomes must be reported separately by the eventual adapter.
 * This interface does not provide a sandbox or power-loss durability by itself.
 */
enum hb_slot { HB_STAGE, HB_LIVE, HB_BACKUP };
enum hb_slot_state { HB_SLOT_ERROR=-1, HB_ABSENT, HB_VALID, HB_INVALID };
enum hb_install_result {
 HB_INSTALLED=0, HB_INSTALLED_CLEANUP_PENDING=1,
 HB_INSTALL_FAILED=-1, HB_INSTALL_CANCELLED=-2, HB_RECOVERY_REQUIRED=-3,
 HB_INSTALL_NO_SPACE=-4, HB_INSTALL_INVALID=-5
};
struct hb_install_io {
 void *context;
 int (*begin)(void *,const char *id);
 void (*end)(void *);
 int (*inspect)(void *,enum hb_slot);
 int (*space)(void *,unsigned long long additional_bytes);
 int (*prepare)(void *); /* Copy package into absent STAGE; may leave partial STAGE. */
 int (*verify)(void *);  /* Check staged package identity, ABI, sizes and hashes. */
 int (*sync)(void *);    /* Flush files and parent directory changes. */
 int (*move)(void *,enum hb_slot,enum hb_slot);
 int (*remove)(void *,enum hb_slot);
 int (*cancelled)(void *);
};
/* Recovery never executes an app or changes a manifest to activate it. */
int hb_install_recover(const struct hb_install_io *,const char *id);
int hb_install_apply(const struct hb_install_io *,const char *id,
                     unsigned long long staged_bytes,unsigned long long reserve_bytes);
#endif
