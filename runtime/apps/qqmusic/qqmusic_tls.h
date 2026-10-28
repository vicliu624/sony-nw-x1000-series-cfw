#ifndef HB_QQMUSIC_TLS_H
#define HB_QQMUSIC_TLS_H
#include "qqmusic_response.h"
#include "qqmusic_resource.h"
#include "../../../sdk/include/x1000/services/tls_stream.h"
enum qq_tls_phase {QQ_TLS_SENDING,QQ_TLS_RECEIVING,QQ_TLS_DONE,QQ_TLS_FAILED};
struct qq_tls_transaction {
 struct qq_response response;
 br_ssl_engine_context *engine;
 struct hb_transfer_deadline *deadline;
 volatile int *stop;
 int fd,error;
 enum qq_tls_phase phase;
 unsigned anonymous_framed_eof;
 char wire[8192];size_t wire_bytes,sent;
};
/* Caller owns connected socket, engine, verifier/trust/entropy/time, deadline
 * and body buffer. Engine must be reset with exact request host. No DNS,
 * default CA, redirects or certificate bypass. Caller cleans crypto and fd. */
int qq_tls_begin(struct qq_tls_transaction *,br_ssl_engine_context *,int fd,
 struct hb_transfer_deadline *,volatile int *stop,const struct qq_request *,
 struct qq_cookie_jar *,uint64_t unix_now,unsigned char *body,size_t capacity);
/* Media profile: validated authorized HTTPS CDN, GET with no account cookies,
 * bounded streaming sink. No redirects. Caller supplies safe staged sink. */
int qq_tls_begin_stream(struct qq_tls_transaction *,br_ssl_engine_context *,int fd,
 struct hb_transfer_deadline *,volatile int *stop,const struct qq_resource *,size_t maximum_bytes,struct qq_response_sink);
/* 0=pending, 1=success after authenticated records and complete framing,
 * -1=failed. Without close_notify, only explicit complete Content-Length or
 * chunked framing may finish (RFC 9112 9.8); EOF-delimited bodies reject.
 * anonymous_framed_eof reports this mode for anonymous requests.
 * wait_cap_ms <=1000. Deadline covers handshake/request/response/close. */
int qq_tls_step(struct qq_tls_transaction *,unsigned wait_cap_ms);
void qq_tls_cancel(struct qq_tls_transaction *);
#endif
