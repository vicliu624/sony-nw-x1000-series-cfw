#ifndef XNOW_RF_INIT_H
#define XNOW_RF_INIT_H
#include <stddef.h>
#include "xnow_session.h"
/* Original w8_proc_init region mapping, with strict input bounds. */
#ifdef __cplusplus
extern "C" {
#endif
int xnow_region_from_nvp(const char *,size_t,unsigned *);
/* Run in the guarded controller's child, not the UI. Uses original nvp zr11/1,
 * iwpriv region/TPC, wlanconfig pa_cfg_ext_set and iwconfig txpower15.
 * Admits INITIALIZE or RESTORE_INITIALIZE in the matching session phase.
 * Caller must verify root tool/config identities before starting. No NVP write
 * operation is provided. Success means tools accepted commands, not RF proof.
 * Errors identify the failed stage; all children are drained, output bounded.
 */
int xnow_rf_initialize(const struct xnow_session *);
#ifdef __cplusplus
}
#endif
#endif
