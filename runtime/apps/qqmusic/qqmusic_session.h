/* Device-side login coordinator. Transport must not log credentials/bodies. */
#ifndef HB_QQMUSIC_SESSION_H
#define HB_QQMUSIC_SESSION_H
#include <stdint.h>
enum qq_state { QQ_IDLE, QQ_QR_WAIT, QQ_QR_SCANNED, QQ_EXCHANGE,
 QQ_VERIFY, QQ_READY, QQ_EXPIRED, QQ_FAILED, QQ_CANCELLED };
enum qq_event { QQ_WAITING, QQ_SCANNED, QQ_AUTHORIZED, QQ_QR_EXPIRED,
 QQ_EXCHANGED, QQ_VERIFIED, QQ_DENIED, QQ_NETWORK_ERROR };
struct qq_session {
 enum qq_state state;
 uint32_t generation;
 uint64_t deadline_ms;
};
void qq_session_init(struct qq_session *s);
/* Each request captures generation; callbacks from old requests are rejected. */
int qq_session_begin(struct qq_session *s, uint64_t now_ms, uint32_t ttl_ms);
int qq_session_event(struct qq_session *s, uint32_t generation,
 enum qq_event event, uint64_t now_ms);
void qq_session_cancel(struct qq_session *s);
int qq_session_tick(struct qq_session *s, uint64_t now_ms);
/* QQ QR token hash, input is a cookie value held only in memory. */
uint32_t qq_qr_token(const unsigned char *value, unsigned length);
#endif
