#ifndef HB_QQMUSIC_RESPONSE_H
#define HB_QQMUSIC_RESPONSE_H
#include "qqmusic_http.h"
#include "../../../sdk/include/x1000/services/sha256.h"
struct qq_response_sink {
 void *opaque;
 int (*write)(void *,const unsigned char *,size_t);
 /* Sync/finish staged source, NOT publish as playable or import stock DB. */
 int (*finish)(void *,uint64_t,const unsigned char sha256[32]);
 void (*abort)(void *);
};
enum qq_response_phase {QQ_RX_HEAD,QQ_RX_FIXED,QQ_RX_CLOSE,QQ_RX_SIZE,
 QQ_RX_CHUNK,QQ_RX_CR,QQ_RX_LF,QQ_RX_TRAILER,QQ_RX_COMPLETE,QQ_RX_DONE,QQ_RX_FAILED};
struct qq_response {
 struct qq_cookie_jar staged,*destination;
 struct qq_http_head head;
 enum qq_response_phase phase;
 char host[128],path[2049],headers[16385],chunk_line[17];
 size_t header_bytes,chunk_used,body_bytes,capacity,wire_bytes;
 uint64_t now,remaining;
 unsigned char *body;
 struct qq_response_sink sink;
 struct hb_sha256 hash;
 unsigned char block[4096],digest[32];size_t block_bytes;
 unsigned streaming,sink_active,anonymous,cgi_framed;
};
/* Caller owns body buffer. Maximum body 256 KiB, total wire limit
 * 4*capacity+32768. Header limit 16 KiB. Chunk extensions/trailers rejected.
 * Binary body (PNG supported) is not NUL terminated. No network IO. */
int qq_response_init(struct qq_response *,struct qq_cookie_jar *,const char *host,
 const char *request_path,uint64_t now,unsigned char *body,size_t capacity);
/* Exact QIMEI endpoint only. Ignores Set-Cookie; never mutates account jars. */
int qq_response_init_qimei(struct qq_response *,unsigned char *,size_t);
/* Fresh GetSession uses no account cookies. Exact musicu origin only. */
int qq_response_init_session(struct qq_response *,unsigned char *,size_t);
int qq_response_init_cover(struct qq_response *,const char *path,unsigned char *,size_t);
/* Fixed QQ musicu POST response. Cookie commit still waits for complete,
 * TLS-authenticated explicit HTTP framing when a peer omits close_notify. */
int qq_response_init_cgi(struct qq_response *,struct qq_cookie_jar *,uint64_t,unsigned char *,size_t);
int qq_response_finish_cgi_eof(struct qq_response *);
/* RFC 9112 9.8: only after authenticated TLS records and socket EOF. Requires
 * complete explicit Content-Length/chunked framing; EOF-delimited rejects. */
int qq_response_finish_framed_eof(struct qq_response *);
/* Cookieless streaming body, max256MiB. Caller authorizes/binds TLS origin.
 * No file implementation supplied; write/finish/abort are required transaction
 * callbacks. No fallback path. Abort called on any subsequent parse failure.
 * Same authenticated close-notify requirement as memory finish(). */
int qq_response_init_stream(struct qq_response *,size_t maximum_bytes,struct qq_response_sink);
/* 0=more input, 1=framing complete, negative=failed (secrets erased).
 * -103 unsupported status, -104 content encoding, -105 duplicate binding header. */
int qq_response_push(struct qq_response *,const unsigned char *,size_t);
/* Only after authenticated TLS close-notify; raw EOF must use cancel().
 * Commits Cookie jar only when the whole response is valid. */
int qq_response_finish(struct qq_response *);
/* Anonymous bootstrap only: caller verified every TLS record and socket EOF.
 * Accept only an already complete Content-Length/chunked message. Never an
 * EOF-delimited body, cookie transaction, media stream or partial response. */
int qq_response_finish_anonymous_eof(struct qq_response *);
void qq_response_cancel(struct qq_response *);
#endif
