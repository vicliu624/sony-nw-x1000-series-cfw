#ifndef HB_QQMUSIC_METADATA_H
#define HB_QQMUSIC_METADATA_H
#include "qqmusic_id3.h"
#include "qqmusic_catalog.h"
#include "qqmusic_resource.h"
enum qq_meta_field {QQ_META_TITLE,QQ_META_ARTIST,QQ_META_ALBUM,QQ_META_ALBUM_ARTIST,QQ_META_TRACK,QQ_META_DISC,QQ_META_DATE,QQ_META_GENRE,QQ_META_COMPOSER,QQ_META_FIELDS};
struct qq_metadata {
 char fields[QQ_META_FIELDS][1025],year[5];
 char extra_names[16][65],extra_values[16][1025];
 unsigned source_mask,filled_mask,extras;
 int error;
 struct qq_id3_extra extra_view[16];
 unsigned char *jpeg;size_t jpeg_capacity,jpeg_bytes;
 char bound_album_mid[65];
 unsigned source_cover,nonfront_pictures;
};
/* Source text first. Unknown comments retained as TXXX (bounded), conflicting
 * duplicate scalar fields fail. Repeated artists joined, never title-matched.
 * Source METADATA_BLOCK_PICTURE front cover uses configured artwork buffer. */
void qq_metadata_init(struct qq_metadata *);
int qq_metadata_comment(struct qq_metadata *,const char *name,size_t,const char *value,size_t);
/* Only matching song/media IDs may supply missing fields; no guessing. */
int qq_metadata_fill(struct qq_metadata *,const struct qq_song *,const struct qq_resource_intent *,const char *verified_album_artist);
int qq_metadata_tags(struct qq_metadata *,struct qq_track_tags *out);
/* Caller-owned artwork buffer must outlive tag generation. No file writes. */
int qq_metadata_artwork_buffer(struct qq_metadata *,unsigned char *,size_t);
/* Album MID must equal the already-bound explicit fallback song album MID.
 * Only fills missing cover; source cover never replaced. */
int qq_metadata_album_cover(struct qq_metadata *,const char *album_mid,const unsigned char *,size_t);
#endif
