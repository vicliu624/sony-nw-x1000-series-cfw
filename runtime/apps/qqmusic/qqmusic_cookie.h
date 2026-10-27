#ifndef HB_QQMUSIC_COOKIE_H
#define HB_QQMUSIC_COOKIE_H
#include <stddef.h>
#include <stdint.h>
#define QQ_COOKIE_LIMIT 64
struct qq_cookie {
 char name[65], value[513], domain[128], path[257];
 uint64_t expires;
 unsigned used, host_only, secure, persistent;
};
struct qq_cookie_jar { struct qq_cookie entries[QQ_COOKIE_LIMIT]; };
/* HTTPS-only login cookie jar. Origin must be an explicit supported service.
 * Input excludes Set-Cookie: prefix. Unix UTC seconds supplied by caller.
 * Error leaves jar unchanged. No persistence or logging. */
int qq_cookie_set(struct qq_cookie_jar *,const char *origin,const char *path,
                  const char *header,size_t bytes,uint64_t now);
/* Output erased on error. Does not evict cookies to fit a header.
 * Ambiguous duplicate names fail closed rather than choosing credentials. */
int qq_cookie_header(const struct qq_cookie_jar *,const char *host,const char *path,
                     uint64_t now,char *out,size_t capacity);
void qq_cookie_clear(struct qq_cookie_jar *);
#endif
