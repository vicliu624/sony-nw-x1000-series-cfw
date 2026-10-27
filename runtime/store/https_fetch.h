#ifndef HB_STORE_HTTPS_FETCH_H
#define HB_STORE_HTTPS_FETCH_H
#include "tls_socket_step.h"
#include "download_file.h"
#include "http_response.h"
enum hb_https_phase {HB_HTTPS_REQUEST,HB_HTTPS_RESPONSE,HB_HTTPS_CLOSING,HB_HTTPS_DONE,HB_HTTPS_FAILED,HB_HTTPS_REDIRECT};
enum hb_https_error {HB_HTTPS_INPUT=-40,HB_HTTPS_DEADLINE=-41,HB_HTTPS_CLOCK=-42,HB_HTTPS_TLS=-43,HB_HTTPS_EOF=-44,HB_HTTPS_IO=-45};
struct hb_https_fetch {
 br_ssl_engine_context *engine;int fd;
 struct hb_download_file *file;struct hb_transfer_deadline *deadline;
 struct hb_http_response response;
 char request[3072];unsigned request_bytes,sent;
 enum hb_https_phase phase;int error,tls_error;
};
/* Engine must already have a proper certificate verifier/trust/time/seed and
 * reset with matching host. Connected fd, file and deadline remain caller-owned.
 * No DNS/connect/redirects here. File is OPEN inactive cache from begin(). */
int hb_https_fetch_init(struct hb_https_fetch *,br_ssl_engine_context *,int,
 struct hb_download_file *,struct hb_transfer_deadline *,const char *host,unsigned port,const char *path);
int hb_https_fetch_init_url(struct hb_https_fetch *,br_ssl_engine_context *,int,
 struct hb_download_file *,struct hb_transfer_deadline *,const char *absolute_https_url);
/* 0=more steps, 1=verified+synced inactive cache, negative=terminal failure.
 * Caller closes transport and discards/reviews cache on failure. Per-call
 * blocking wait capped1000ms; filesystem syscalls cannot be preempted here. */
int hb_https_fetch_step(struct hb_https_fetch *,unsigned wait_cap_ms);
#endif
