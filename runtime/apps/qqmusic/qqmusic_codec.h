#ifndef HB_QQMUSIC_CODEC_H
#define HB_QQMUSIC_CODEC_H
#include <stddef.h>
#include <stdint.h>
struct qq_codec_io {
 void *source,*destination;
 uint64_t source_bytes;
 int (*read_at)(void *,uint64_t,unsigned char *,unsigned);
 int (*write)(void *,const unsigned char *,unsigned);
 volatile int *stop;
 /* Optional source-comment visitor, followed by one done callback before MP3
  * bytes. Both or neither required. Failure aborts conversion. */
 void *metadata;
 int (*comment)(void *,const char *,size_t,const char *,size_t);
 int (*comments_done)(void *);
 void *progress_context;int (*progress)(void *,uint64_t samples,uint64_t total);
};
struct qq_codec_report {uint64_t samples,mp3_bytes;unsigned rate,channels,padded_samples;};
/* Vorbis -> PCM16 -> MP3, callback IO only. Caller holds protected user-volume
 * transactions; this module never opens paths. Single logical Vorbis stream,
 * mono/stereo, 32/44.1/48kHz initially. Explicit failure for other formats.
 * On error output is incomplete and MUST be aborted by caller, never published.
 * Decoder heap/resource and physical-device performance are not yet qualified. */
int qq_codec_vorbis_mp3(struct qq_codec_io *,unsigned bitrate_kbps,struct qq_codec_report *);
/* QMC/musicex source -> on-demand decrypted Vorbis -> MP3. ekey comes from
 * current authorization. Source bytes remain untouched; key context is erased.
 * No intermediate plaintext file or source overwrite. No tag merge here. */
int qq_codec_qmc_vorbis_mp3(struct qq_codec_io *,const char *ekey,size_t ekey_bytes,
 unsigned bitrate_kbps,struct qq_codec_report *);
#endif
