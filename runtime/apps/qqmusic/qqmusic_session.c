#include "qqmusic_session.h"
#include <limits.h>
void qq_session_init(struct qq_session *s) {
 s->state=QQ_IDLE; s->generation=0; s->deadline_ms=0;
}
static int active(enum qq_state state) {
 return state==QQ_QR_WAIT || state==QQ_QR_SCANNED ||
        state==QQ_EXCHANGE || state==QQ_VERIFY;
}
int qq_session_begin(struct qq_session *s, uint64_t now, uint32_t ttl) {
 /* Never recycle generation IDs: a stale callback must never authenticate. */
 if (!ttl || ttl>600000 || s->generation==UINT32_MAX ||
     now>UINT64_MAX-ttl) return -1;
 s->generation++; s->deadline_ms=now+ttl; s->state=QQ_QR_WAIT;
 return 0;
}
int qq_session_tick(struct qq_session *s, uint64_t now) {
 if (active(s->state) && now>=s->deadline_ms) {
  s->state=QQ_EXPIRED; s->deadline_ms=0; return 1;
 }
 return 0;
}
void qq_session_cancel(struct qq_session *s) {
 s->state=QQ_CANCELLED; s->deadline_ms=0;
}
int qq_session_event(struct qq_session *s, uint32_t generation,
 enum qq_event e, uint64_t now) {
 if (generation!=s->generation || !active(s->state)) return -1;
 if (qq_session_tick(s,now)) return -1;
 if (e==QQ_DENIED || e==QQ_NETWORK_ERROR) {
  s->state=QQ_FAILED; s->deadline_ms=0; return 0;
 }
 switch(s->state) {
 case QQ_QR_WAIT:
 case QQ_QR_SCANNED:
  if(e==QQ_WAITING) return 0; /* Out-of-order polling cannot unscan QR. */
  if(e==QQ_SCANNED) { s->state=QQ_QR_SCANNED; return 0; }
  if(e==QQ_AUTHORIZED) { s->state=QQ_EXCHANGE; return 0; }
  if(e==QQ_QR_EXPIRED) { s->state=QQ_EXPIRED; s->deadline_ms=0; return 0; }
  break;
 case QQ_EXCHANGE:
  if(e==QQ_EXCHANGED) { s->state=QQ_VERIFY; return 0; }
  break;
 case QQ_VERIFY:
  if(e==QQ_VERIFIED) { s->state=QQ_READY; s->deadline_ms=0; return 0; }
  break;
 default: break;
 }
 return -1;
}
uint32_t qq_qr_token(const unsigned char *value, unsigned length) {
 uint32_t hash=0; unsigned i;
 for(i=0;i<length;i++) hash=hash*33u+value[i];
 return hash&0x7fffffffu;
}
