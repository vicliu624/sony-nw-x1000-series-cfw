#ifndef HB_QQMUSIC_PROTOCOL_H
#define HB_QQMUSIC_PROTOCOL_H
#include "qqmusic_session.h"
#include <stddef.h>
#define QQ_CALLBACK_MAX 8192u
/* These objects contain secrets. Never log them; clear on cancel/error/close. */
struct qq_poll_result { enum qq_event event; char uin[21], sigx[513]; };
struct qq_request {
 const char *host; const char *method;
 unsigned json_body;
 /* Fixed anonymous QIMEI service profile, never arbitrary extra headers. */
 unsigned qimei;
 unsigned anonymous_session;
 unsigned album_cover;
 char qimei_time[21],qimei_sign[33];
 char path[2049], cookie[2049], body[6145];
};
void qq_secret_clear(void *memory, size_t bytes);
/* Complete, bounded ptuiCB response only, never JavaScript evaluation.
 * Failure clears output. Unknown status codes fail closed. */
int qq_parse_poll(const char *body, size_t bytes, struct qq_poll_result *out);
int qq_build_qr(struct qq_request *, uint32_t nonce);
int qq_build_poll(struct qq_request *, const char *qrsig, uint64_t unix_ms);
int qq_build_check_sig(struct qq_request *, const struct qq_poll_result *);
/* p_uin and p_skey must be actual check_sig response cookies, not synthesized.
 * Other response cookies may also be needed; cookie jar integration is pending. */
int qq_build_authorize(struct qq_request *, const char *p_uin, const char *p_skey,
                       const char *state, const char *ui, uint64_t unix_ms);
/* Only exact HTTPS y.qq.com callback path, code and matching state accepted.
 * Does not follow Location. Output is erased on failure. */
int qq_parse_oauth_location(const char *, size_t, const char *expected_state,
                            char *code, size_t capacity);
#endif
