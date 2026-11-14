#ifndef WR_SESSION_WIRE_H
#define WR_SESSION_WIRE_H
#include <stdint.h>
#include <stddef.h>
#define WR_SESSION_BYTES 64u
struct wr_session_progress {uint32_t status,control,library;};
/* Application handshake over an already paired transport. Caller supplies a
 * fresh unpredictable16-byte challenge; no keys or player grants are exchanged. */
#ifdef __cplusplus
extern "C" {
#endif
int wr_session_request(void *,size_t,const uint8_t[16],const uint8_t[32]);
int wr_session_request_read(uint8_t[16],const void *,size_t,const uint8_t[32]);
int wr_session_reply(void *,size_t,const uint8_t[16],uint64_t,const uint8_t[32]);
int wr_session_reply_read(uint64_t *,const void *,size_t,const uint8_t[16],const uint8_t[32]);
int wr_session_resume_request(void *,size_t,const uint8_t[16],const uint8_t[32]);
int wr_session_resume_request_read(uint8_t[16],const void *,size_t,const uint8_t[32]);
int wr_session_resume_reply(void *,size_t,const uint8_t[16],uint64_t,const struct wr_session_progress *,const uint8_t[32]);
int wr_session_resume_reply_read(uint64_t *,struct wr_session_progress *,const void *,size_t,const uint8_t[16],const uint8_t[32]);
#ifdef __cplusplus
}
#endif
#endif
