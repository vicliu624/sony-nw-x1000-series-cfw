#ifndef HB_QQMUSIC_EXPORT_H
#define HB_QQMUSIC_EXPORT_H
#include "qqmusic_catalog.h"
#include "qqmusic_resource.h"
struct qq_export_plan {char relative[513],identity[65];unsigned version;};
/* Relative path only, below a separately verified stock music destination.
 * Does not choose MUSIC/OMGAUDIO or grant write permission. UTF-8 components
 * limited60 display bytes plus stable full identity hashes, FAT-safe names.
 * No I/O; caller must use protected user-volume file transaction. */
int qq_export_plan(const struct qq_song *,const struct qq_resource_intent *,
 const char *album_artist,struct qq_export_plan *);
enum qq_export_existing {QQ_EXPORT_NEW,QQ_EXPORT_REUSE,QQ_EXPORT_CONFLICT};
/* REUSE requires exact resource identity and verified existing file SHA256.
 * Caller actually reads/hashes existing file; no overwrite decision exists. */
int qq_export_existing_check(const struct qq_export_plan *,int exists,
 const char *recorded_identity,const unsigned char recorded_sha[32],const unsigned char actual_sha[32]);
#endif
