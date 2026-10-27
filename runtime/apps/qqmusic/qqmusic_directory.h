#ifndef HB_QQMUSIC_DIRECTORY_H
#define HB_QQMUSIC_DIRECTORY_H
#include "qqmusic_volume.h"
#include "qqmusic_export.h"
struct qq_export_directory {struct qq_volume volume;char filename[256];};
void qq_export_directory_init(struct qq_export_directory *);
/* Creates/reuses the two planned artist/album directories below an already
 * qualified music root. Never chooses MUSIC automatically or creates files.
 * Plan budgets at least two directory units. Exclusive application ownership
 * required. Result pins/revalidates the existing album directory. Existing
 * files/symlinks are rejected, never replaced/deleted. On failure newly created
 * empty directories can remain on user storage for later explicit cleanup. */
int qq_export_directory_open(struct qq_export_directory *,struct qq_volume *root,
 const struct qq_storage_plan *,const struct qq_export_plan *);
int qq_export_directory_close(struct qq_export_directory *);
#endif
