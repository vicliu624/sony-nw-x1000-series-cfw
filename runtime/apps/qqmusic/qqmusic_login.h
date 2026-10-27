#ifndef HB_QQMUSIC_LOGIN_H
#define HB_QQMUSIC_LOGIN_H
#include "qqmusic_response.h"
#include "qqmusic_credential.h"
enum qq_login_stage {QQ_LOGIN_IDLE,QQ_LOGIN_QR,QQ_LOGIN_POLL,QQ_LOGIN_SIG,
 QQ_LOGIN_OAUTH,QQ_LOGIN_CGI,QQ_LOGIN_VERIFY,QQ_LOGIN_DONE,QQ_LOGIN_FAILED};
struct qq_login {
 struct qq_session session;
 struct qq_cookie_jar cookies;
 struct qq_credential credential;
 struct qq_json json;
 enum qq_login_stage stage;
 uint64_t serial,pending,poll_at,last_ms,service_code;
 int error;
 char comm[1025],state[129],ui[65],authorization_code[513];
 struct qq_poll_result authorization;
 unsigned char qr[65536];size_t qr_bytes;
};
/* New/cleared object only. Never reinitialize a live object: IDs must not reset. */
void qq_login_init(struct qq_login *);
/* comm is caller-supplied Android identity/version policy, not an imported
 * account/session. Caller generates fresh unpredictable state and ui.
 * TTL absolute across entire login; now_ms is monotonic, unix_ms is wall time. */
int qq_login_begin(struct qq_login *,const char *comm,size_t comm_bytes,
 const char *state,const char *ui,uint64_t now_ms,uint32_t ttl_ms);
/* 1=request produced and ticket assigned, 0=pending/not due/done, -1=error. */
int qq_login_next(struct qq_login *,uint64_t now_ms,uint64_t unix_ms,
 struct qq_request *,uint64_t *ticket);
/* Accept only authenticated, complete QQ_RX_DONE responses from TLS adapter.
 * Stale ticket rejected without modifying current state. Accepted response
 * body/metadata erased after consumption. Cookie jar used by TLS must be
 * this object's cookies. */
int qq_login_accept(struct qq_login *,uint64_t ticket,uint64_t now_ms,
 struct qq_response *);
void qq_login_cancel(struct qq_login *);
/* Secret JSON, derived from current QR credential. No persistence/logging.
 * VERIFY phase is allowed for service verification; catalog caller must also
 * require QQ_READY. Output wiped on error. */
int qq_login_authenticated_comm(const struct qq_login *,char *,size_t);
#endif
