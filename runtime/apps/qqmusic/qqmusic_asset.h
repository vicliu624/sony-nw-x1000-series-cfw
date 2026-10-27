#ifndef HB_QQMUSIC_ASSET_H
#define HB_QQMUSIC_ASSET_H
#include "qqmusic_volume.h"
#include <stddef.h>
/* Existing, mount-verified user directory only. Exact size and trusted digest
 * are application policy, never values learned from the asset itself. */
int qq_asset_read(struct qq_volume *,const struct qq_storage_plan *,const char *name,
 size_t size,const unsigned char digest[32],unsigned char **out);
void qq_asset_free(unsigned char *,size_t);
/* Receipt from a fixed-hash, bounded streaming verification. File mapping is
 * read-only MAP_PRIVATE, not a font-sized anonymous allocation. Resources must
 * remain immutable while the app runs (no concurrent USB/update writes). */
struct qq_asset_mapping {unsigned char *data;size_t bytes;unsigned char digest[32];};
int qq_asset_map(struct qq_volume *,const struct qq_storage_plan *,const char *,size_t,const unsigned char[32],struct qq_asset_mapping *);
int qq_asset_unmap(struct qq_asset_mapping *);
#endif
