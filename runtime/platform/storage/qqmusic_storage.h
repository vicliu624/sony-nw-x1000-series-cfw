#ifndef HB_QQMUSIC_STORAGE_H
#define HB_QQMUSIC_STORAGE_H
#include <stddef.h>
#include <stdint.h>
struct qq_storage_policy {const char *source,*filesystem;};
enum qq_mount_reason {QQ_MOUNT_OK,QQ_MOUNT_INPUT,QQ_MOUNT_ROW,
 QQ_MOUNT_ROOT,QQ_MOUNT_USER_DUPLICATE,QQ_MOUNT_SOURCE,
 QQ_MOUNT_FILESYSTEM,QQ_MOUNT_READONLY,QQ_MOUNT_NESTED,QQ_MOUNT_MISSING};
/* Safe numeric startup diagnostic; no data writes or account information. */
int qq_storage_mount_reason(const struct qq_storage_policy *,const char *,size_t);
/* Normalized observations, not Sony ABI structs. Must include /, /contents,
 * then every existing directory prefix down to the intended parent. */
struct qq_storage_directory {const char *path;uint64_t device;unsigned mode;};
struct qq_storage_plan {
 uint64_t source,decoded,mp3,temporary,artwork,metadata,reserve;
 uint64_t allocation_unit,available_units;
 /* Number of planned files in each of the first six categories; directory
  * allocation budget is separate. Do not group small files as one file. */
 uint64_t files[6],directory_units;
};
enum qq_storage_error {QQ_STORAGE_INPUT=-1,QQ_STORAGE_MOUNT=-2,
 QQ_STORAGE_BOUNDARY=-3,QQ_STORAGE_SPACE=-4,QQ_STORAGE_OVERFLOW=-5};
/* Pure preflight, no filesystem IO. Mount data is caller-read /proc/mounts,
 * observed directory stats and space must come from the SAME user volume.
 * No system fallback. Does NOT prevent concurrent unmount/path replacement;
 * future writer must pin directory descriptors and revalidate before writes.
 * On success required is cluster-rounded peak bytes INCLUDING retained source.
 * Must be called per transaction; this is not an enduring write capability. */
int qq_storage_preflight(const struct qq_storage_policy *,const char *mounts,size_t,
 const struct qq_storage_directory *,size_t,const struct qq_storage_plan *,uint64_t *required);
#endif
