#ifndef XNOW_SESSION_H
#define XNOW_SESSION_H
/* Serialized radio transaction policy. The platform runner executes actions;
 * this module does not execute commands, access files or change radio state.
 * Completion means the platform operation has returned AND its worker drained.
 * Never report cancellation alone as completion of a blocking Sony request.
 */
enum xnow_session_action {
    XNOW_SESSION_NONE, XNOW_SESSION_PREFLIGHT, XNOW_SESSION_ACQUIRE,
    XNOW_SESSION_INSPECT, XNOW_SESSION_DISCONNECT, XNOW_SESSION_UNLOAD,
    XNOW_SESSION_LOAD_CANDIDATE, XNOW_SESSION_WAKE, XNOW_SESSION_INITIALIZE, XNOW_SESSION_VERIFY_CANDIDATE,
    XNOW_SESSION_CONFIGURE, XNOW_SESSION_RESTORE_UNLOAD,
    XNOW_SESSION_LOAD_STOCK, XNOW_SESSION_RESTORE_WAKE, XNOW_SESSION_RESTORE_INITIALIZE, XNOW_SESSION_VERIFY_STOCK,
    XNOW_SESSION_RECONNECT, XNOW_SESSION_RELEASE
};
enum xnow_session_phase {
    XNOW_SESSION_STARTING, XNOW_SESSION_READY, XNOW_SESSION_STOPPING,
    XNOW_SESSION_DONE, XNOW_SESSION_REPAIR_REQUIRED
};
struct xnow_session {
    enum xnow_session_action next, pending;
    enum xnow_session_phase phase;
    unsigned allow_disconnect, cancelled, lease, changed, was_connected;
    int failure, restore_failure;
};
#ifdef __cplusplus
extern "C" {
#endif
void xnow_session_init(struct xnow_session *,unsigned allow_disconnect);
/* Returns an action once; further calls return NONE until complete(). */
enum xnow_session_action xnow_session_take(struct xnow_session *);
/* All actions: zero success, negative failure. INSPECT alone returns original
 * public cnmgr state 3 (ready) or 4 (connected). Other states are refused.
 * Existing connected Wi-Fi may only be disrupted with allow_disconnect.
 */
int xnow_session_complete(struct xnow_session *,enum xnow_session_action,int);
void xnow_session_stop(struct xnow_session *);
/* Retains the manager lease on uncertain restoration. Explicit retry only. */
int xnow_session_retry_restore(struct xnow_session *);
#ifdef __cplusplus
}
#endif
#endif
