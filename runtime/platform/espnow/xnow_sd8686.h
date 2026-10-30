#ifndef XNOW_SD8686_H
#define XNOW_SD8686_H
#include "xnow_mailbox.h"
#include "xnow_session.h"
struct xnow_sd8686 {int fd,verified;};
/* Requires exact compiled bridge and reserved 3-block pool already loaded.
 * Does not install/reload anything. Never use across driver reset/sleep/USB.
 */
#ifdef __cplusplus
extern "C" {
#endif
int xnow_sd8686_open(struct xnow_sd8686 *,struct xnow_mailbox *);
void xnow_sd8686_close(struct xnow_sd8686 *);
/* Read-only original pool metadata; no arbitrary address API. */
int xnow_sd8686_pool_info(uint32_t *stride,uint32_t *count,uint32_t *free_blocks);
/* GET is read-only on the matching original driver. SET is experimental and
 * requires an acquired session's outstanding CONFIGURE action plus a verified
 * candidate adapter. It reads the channel back; error may mean partial change.
 * No production app invokes SET yet. Does not wake or power on the radio.
 */
int xnow_sd8686_channel_get(unsigned *);
int xnow_sd8686_channel_set(struct xnow_sd8686 *,const struct xnow_session *,unsigned);
/* Original driver's deepsleep0 followed by deepsleep2 query. Requires WAKE
 * or RESTORE_WAKE session action. Query must report off; code verification follows.
 * Does not claim to exit every radio power-save mode. No app invokes this yet.
 */
int xnow_sd8686_wake(const struct xnow_session *);
/* Read-only postcondition for stock unload: all four wireless modules absent.
 * Does not prevent a stock service from subsequently reloading them.
 */
int xnow_sd8686_modules_absent(void);
/* Matching stock four-block layout plus SHA-256 of276 stable code/layout
 * bytes. Read-only, not complete RAM attestation. Requires original-image
 * loading to have passed independent file/ownership checks. */
int xnow_sd8686_stock_verify(void);
#ifdef __cplusplus
}
#endif
#endif
