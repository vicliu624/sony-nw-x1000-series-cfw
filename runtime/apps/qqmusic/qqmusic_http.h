#ifndef HB_QQMUSIC_HTTP_H
#define HB_QQMUSIC_HTTP_H
#include "qqmusic_cookie.h"
#include "qqmusic_protocol.h"
struct qq_http_head {
 unsigned status,has_length,chunked;
 uint64_t length;
 char location[2049],content_type[129];
 uint64_t server_date;unsigned has_date;
};
/* Complete header block required (16 KiB limit). consumed gives body offset.
 * No network IO or automatic redirects. Commit cookies only after full success.
 * Caller must provide authenticated HTTPS origin and bounded body framing. */
int qq_http_parse_head(const char *,size_t,const char *host,const char *path,
                       uint64_t now,struct qq_cookie_jar *,struct qq_http_head *,size_t *consumed);
/* jar=NULL is a cookieless response profile: Set-Cookie ignored, no origin
 * validation here. Media transport MUST bind/validate the authorized CDN host
 * itself before network IO. No cookie changes or redirect following. */
/* Serializes GET/POST into caller-owned secret buffer, no IO. Cookie comes
 * exclusively from scoped jar, not request.cookie. Error erases output. */
int qq_http_request_wire(const struct qq_request *,const struct qq_cookie_jar *,
                         uint64_t now,char *out,size_t cap,size_t *bytes);
/* Fixed public album artwork endpoint, no caller URL or account cookies. */
int qq_build_album_cover(struct qq_request *,const char *album_mid);
int qq_http_album_cover_path_valid(const char *);
#endif
