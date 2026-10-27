#ifndef HB_STORE_HTTP_RESPONSE_H
#define HB_STORE_HTTP_RESPONSE_H
#include "download_stream.h"
enum hb_http_state {HB_HTTP_STATUS,HB_HTTP_HEADERS,HB_HTTP_FIXED,HB_HTTP_CLOSE,HB_HTTP_CHUNK_SIZE,HB_HTTP_CHUNK_DATA,HB_HTTP_CHUNK_CR,HB_HTTP_CHUNK_LF,HB_HTTP_TRAILERS,HB_HTTP_COMPLETE,HB_HTTP_DONE,HB_HTTP_FAILED,HB_HTTP_REDIRECT};
enum hb_http_error {HB_HTTP_STATUS_ERROR=-20,HB_HTTP_HEADER_ERROR=-21,HB_HTTP_FRAMING_ERROR=-22,HB_HTTP_TRUNCATED=-23};
struct hb_http_response {
 struct hb_download_stream *body;
 enum hb_http_state state;
 unsigned used,header_bytes,wire_bytes,remaining;
 int cr,has_length,chunked,error;
 char line[3073];
 unsigned status;int allow_redirects;char location[2400];
};
/* Restricted GET response profile: 200 by default; an explicit caller may opt
 * into bounded HTTPS Location parsing for redirect responses. Identity encoding,
 * duplicate Content-Length or chunk extensions. Supports length/chunked/EOF.
 * 1024-byte lines (3072 with redirects), 8192-byte headers+trailers. */
int hb_http_response_init(struct hb_http_response *,struct hb_download_stream *);
int hb_http_response_push(struct hb_http_response *,const unsigned char *,unsigned);
int hb_http_response_finish(struct hb_http_response *);
#endif
