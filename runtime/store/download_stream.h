#ifndef HB_STORE_DOWNLOAD_STREAM_H
#define HB_STORE_DOWNLOAD_STREAM_H
#include "../native/sha256.h"
enum hb_download_error {HB_DOWNLOAD_INPUT=-1,HB_DOWNLOAD_IO=-2,HB_DOWNLOAD_CANCELLED=-3,HB_DOWNLOAD_HASH=-4,HB_DOWNLOAD_SIZE=-5};
enum hb_download_state {HB_DOWNLOAD_ACTIVE,HB_DOWNLOAD_VERIFIED,HB_DOWNLOAD_FAILED};
struct hb_download_stream {
 struct hb_sha256 hash;
 unsigned expected,received;
 unsigned char digest[32];
 enum hb_download_state state;
 int error;
 void *context;
 int (*write)(void *,const unsigned char *,unsigned);
 volatile int *stop;
};
/* Data must already be decoded HTTP body bytes. Size/hash come from the
 * selected package metadata, not an untrusted Content-Length. Max128MiB/file.
 * Sink is an inactive temporary file; owner must clean it after any failure. */
int hb_download_stream_init(struct hb_download_stream *,unsigned expected,
 const unsigned char *digest,void *,int (*write)(void *,const unsigned char *,unsigned),volatile int *stop);
int hb_download_stream_push(struct hb_download_stream *,const unsigned char *,unsigned);
/* Only successful finish sets VERIFIED. No rename/activation/fsync here. */
int hb_download_stream_finish(struct hb_download_stream *);
#endif
