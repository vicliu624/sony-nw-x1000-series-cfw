#ifndef WR_SESSION_WIRE_H
#define WR_SESSION_WIRE_H
#include <stdint.h>
#include <stddef.h>
#define WR_SESSION_BYTES 64u
/* Application handshake over an already paired transport. Caller supplies a
 * fresh unpredictable16-byte challenge; no keys or player grants are exchanged. */
#ifdef __cplusplus
extern "C" {
#endif
int wr_session_request(void *,size_t,const uint8_t[16],const uint8_t[32]);
int wr_session_request_read(uint8_t[16],const void *,size_t,const uint8_t[32]);
int wr_session_reply(void *,size_t,const uint8_t[16],uint64_t,const uint8_t[32]);
int wr_session_reply_read(uint64_t *,const void *,size_t,const uint8_t[16],const uint8_t[32]);
#ifdef __cplusplus
}
#endif
#endif
