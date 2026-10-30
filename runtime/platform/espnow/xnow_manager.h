#ifndef XNOW_MANAGER_H
#define XNOW_MANAGER_H
#include "xnow_session.h"
#include <stdint.h>
/* Original libcnmgr client, owned by one controller PROCESS. These calls can
 * block on original IPC/events: never invoke on a display/UI thread. The owner
 * process must stay alive and retain its client until all operations complete.
 * No kill-on-timeout, early fin, raw daemon commands or saved-network structs.
 */
enum {XNOW_CURRENT_CONFIG_BYTES=1004,XNOW_MANAGER_CONFIG_UNAVAILABLE=-20};
/* Opaque original configuration can contain credentials. RAM only: never log
 * or serialize this object. The official API's size/copy path is JP1.11-specific.
 */
struct xnow_manager {
    int owner,held,executing,uncertain,current_valid,capture_result;
    union {uint32_t alignment[XNOW_CURRENT_CONFIG_BYTES/4];unsigned char bytes[XNOW_CURRENT_CONFIG_BYTES];} current;
};
#ifdef __cplusplus
extern "C" {
#endif
void xnow_manager_init(struct xnow_manager *);
/* Existing FIFO/mount checks only. This is not an exclusive radio/USB lease. */
int xnow_manager_stock_ipc_guard(void *,enum xnow_session_action);
/* Execute only the session's current ACQUIRE/INSPECT/DISCONNECT/RECONNECT/RELEASE.
 * guard must validate original RAM-backed IPC, not create replacement files.
 * No other action is admitted. INSPECT returns the public state; other actions
 * return0 on success. Does not modify the session; caller reports completion.
 */
int xnow_manager_execute(struct xnow_manager *,const struct xnow_session *,void *,
                          int (*guard)(void *,enum xnow_session_action));
#ifdef __cplusplus
}
#endif
#endif
