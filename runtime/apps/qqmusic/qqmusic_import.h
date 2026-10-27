#ifndef HB_QQMUSIC_IMPORT_H
#define HB_QQMUSIC_IMPORT_H
#include "qqmusic_codec.h"
#include "qqmusic_metadata.h"
struct qq_import_conversion {
 struct qq_codec_io io;
 const struct qq_song *song;const struct qq_resource_intent *intent;
 const char *album_artist,*ekey;size_t ekey_bytes;
 unsigned bitrate_kbps,encrypted;
 uint64_t maximum_output;
 unsigned char *artwork;size_t artwork_capacity;
 const char *cover_album_mid;const unsigned char *cover;size_t cover_bytes;
 /* Optional synchronous worker callback, invoked only after source comments
  * prove the front cover is missing. Exact bound album MID, encoded image in
  * bounded caller buffer. No title lookup or overriding a source image. */
 void *cover_context;
 int (*fetch_cover)(void *,const char *,unsigned char *,size_t,size_t *);
};
struct qq_import_report {struct qq_codec_report audio;uint64_t output_bytes;size_t tag_bytes,cover_bytes;unsigned source_fields,filled_fields,source_cover;};
/* Conversion into caller-owned protected output transaction. Source comments
 * precede exact-ID fallback, then ID3v2.3 precedes MP3. No file paths, source
 * writes, publication or retained ekey. Caller MUST abort incomplete output on
 * any failure, and preserve original download. No existing metadata callbacks.
 * encrypted0 is explicit Vorbis input, not automatic decryption fallback. */
int qq_import_convert(const struct qq_import_conversion *,struct qq_import_report *);
#endif
