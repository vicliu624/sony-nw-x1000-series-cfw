/* Host-test bridge only; never linked into the ARM app. */
#include "../../runtime/store/stock_fs_bridge.h"
#include <sys/stat.h>
int hb_target_fstat(int fd, struct hb_target_stat *out) {
  struct stat s;
  if (fstat(fd, &s))
    return -1;
  out->st_dev = s.st_dev;
  out->st_size = s.st_size;
  out->st_ino = s.st_ino;
  out->st_mode = s.st_mode;
  out->st_nlink = s.st_nlink;
  return 0;
}
