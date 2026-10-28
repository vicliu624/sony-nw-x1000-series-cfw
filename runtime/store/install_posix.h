#ifndef HB_STORE_INSTALL_POSIX_H
#define HB_STORE_INSTALL_POSIX_H
#include "transaction.h"
/* Experimental unified local-package adapter, not a device build. Canonical
 * existing apps root and separate immutable source package; no archive/network.
 * Serial caller; original Sony lifecycle is outside this library. */
int hb_store_install_local(const char *apps_root,const char *source,const char *id,
                            unsigned long long reserve_bytes,volatile int *stop);
/* Optional exact scanned package identity, checked before transaction writes. */
int hb_store_install_local_expected(const char *,const char *,const char *,
 unsigned long long,volatile int *,const unsigned char *expected_identity);
/* live_present -1 disables the guard; 0 expects absence; 1 exact verified bundle.
 * Checked under the install lock before recovery/staging can change any app. */
int hb_store_install_local_guarded(const char *,const char *,const char *,
 unsigned long long,volatile int *,const unsigned char *incoming_identity,
 int live_present,const unsigned char *live_identity);
int hb_store_recover_local(const char *apps_root,const char *id,volatile int *stop);
/* Explicit user choice only: cancel idle metadata when STAGE/BACKUP are absent.
 * Existing LIVE must fully validate; conflicting valid records are refused.
 * No application, source, save or directory is removed by this operation. */
int hb_store_cancel_idle_local(const char *apps_root,const char *id,volatile int *stop);
#endif
