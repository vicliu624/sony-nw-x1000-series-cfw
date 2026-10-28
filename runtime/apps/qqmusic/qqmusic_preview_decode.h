#ifndef HB_QQMUSIC_PREVIEW_DECODE_H
#define HB_QQMUSIC_PREVIEW_DECODE_H
#include "qqmusic_codec.h"
struct qq_preview_sink {
 void *context;
 int (*format)(void *,unsigned rate,unsigned channels);
 /* Borrowed interleaved signed PCM16 little-endian, at most4096 bytes.
  * Consumer must accept all bytes or return failure; never silently drop. */
 int (*pcm)(void *,const unsigned char *,unsigned bytes);
};
struct qq_preview_report {uint64_t samples;unsigned rate,channels,limited;};
/* Complete protected source supplied by the storage/authorization owner.
 * No paths, device calls, MP3 encoding or persistence. A maximum30-second
 * decoded prefix, not a wall-clock timeout. Decoder does not own audio routes.
 * Return0 complete prefix/EOF,-2 cancelled,-1 error; report cleared on error.
 * encrypted0 explicitly means ordinary Vorbis, never a decryption fallback. */
int qq_preview_decode(struct qq_codec_io *source,unsigned encrypted,
 const char *ekey,size_t ekey_bytes,unsigned maximum_ms,
 const struct qq_preview_sink *,struct qq_preview_report *);
#endif
