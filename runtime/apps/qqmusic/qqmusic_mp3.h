#ifndef HB_QQMUSIC_MP3_H
#define HB_QQMUSIC_MP3_H
#include "qqmusic_import.h"
struct qq_mp3_report {uint64_t frames;unsigned bitrate_kbps;};
/* Read-back structural check for this encoder's ID3v2.3 + MPEG1 Layer3 output.
 * Checks every tag/frame boundary and conversion sample/byte counts. Not an
 * audio decoder or proof of physical Sony indexing. No writes or allocation. */
int qq_mp3_verify(const struct qq_codec_io *,const struct qq_import_report *,struct qq_mp3_report *);
#endif
