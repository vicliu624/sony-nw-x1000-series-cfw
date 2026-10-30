#ifndef XNOW_FILE_CHECK_H
#define XNOW_FILE_CHECK_H
#include <stdint.h>
/* Read-only hash/identity check. Every directory component is opened without
 * following symlinks. expected_device must be an independently observed mount
 * device; this function does not establish USB ownership or mount policy.
 * Only exact absolute paths are admitted. No directory/file is created.
 */
#ifdef __cplusplus
extern "C" {
#endif
int xnow_file_check(const char *path,uint64_t expected_device,unsigned bytes,
                    const unsigned char sha256[32]);
#ifdef __cplusplus
}
#endif
#endif
