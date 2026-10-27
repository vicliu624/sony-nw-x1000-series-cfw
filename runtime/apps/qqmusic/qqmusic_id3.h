#ifndef HB_QQMUSIC_ID3_H
#define HB_QQMUSIC_ID3_H
#include <stddef.h>
struct qq_id3_extra {const char *name,*value;};
struct qq_track_tags {
 const char *title,*artist,*album,*album_artist,*track,*disc,*year;
 const unsigned char *jpeg;size_t jpeg_bytes;
 const char *genre,*composer,*date;
 const struct qq_id3_extra *extras;size_t extra_count;
};
/* New ID3v2.3.0 tag only, no audio or filesystem modification.
 * UTF-8 text -> UTF-16LE with BOM. Text <=4096 input bytes each, tag <=1 MiB.
 * Caller supplies independently validated JPEG; marker checks here are not
 * an image decoder. Missing fields are omitted. Failure clears entire output.
 * Source metadata matching/preservation belongs to the import transaction. */
int qq_id3_build(const struct qq_track_tags *,unsigned char *out,size_t capacity,size_t *bytes);
#endif
