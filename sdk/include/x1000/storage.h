#ifndef X1000_SDK_STORAGE_H
#define X1000_SDK_STORAGE_H
#include "app.h"
#ifdef __cplusplus
extern "C" {
#endif
enum xw_storage_result {
  XW_STORAGE_OK = 0,
  XW_STORAGE_MISSING = 1,
  XW_STORAGE_INVALID = -1,
  XW_STORAGE_OWNERSHIP = -2,
  XW_STORAGE_BOUNDARY = -3,
  XW_STORAGE_SPACE = -4,
  XW_STORAGE_IO = -5,
  XW_STORAGE_UNCERTAIN = -6,
  XW_STORAGE_STOPPED = -7
};
/* Returns 1 only while original-platform coordination establishes exclusive
 * player ownership. 0/negative is unknown/busy. An ioctl zero, a lock, or a
 * user assertion alone is not proof. Default device provider is unknown (fail
 * closed). Supplying a provider is advanced integration, not a sandbox
 * permission. */
typedef int (*xw_storage_owner)(void *);
int xw_storage_set_owner(xw_app *, xw_storage_owner, void *);
/* Fixed /contents/HOMEBREW/data/<id>, pre-provisioned by the computer. Flat
 * safe names, <=64KiB/file, 1MiB free reserve. No fallback, links, or system
 * writes. Atomic temp+fsync+rename; UNCERTAIN means rename happened but
 * durability or post-operation ownership cannot be established. Never retry
 * blindly. */
int xw_data_read(xw_app *, const char *name, void *, size_t capacity,
                 size_t *size);
int xw_data_write(xw_app *, const char *name, const void *, size_t size);
/* Read-only packaged assets/<name>, flat safe names, <=1MiB. */
int xw_resource_read(xw_app *, const char *name, void *, size_t capacity,
                     size_t *size);
#ifdef __cplusplus
}
#endif
#endif
