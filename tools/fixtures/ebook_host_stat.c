/* Host tests only. Production links the independently verified old-Sony bridge.
 */
#include "../../runtime/store/stock_fs_bridge.h"
#include <sys/stat.h>
static int cv(const struct stat *s, struct hb_target_stat *out) {
  out->st_dev = s->st_dev;
  out->st_size = s->st_size;
  out->st_ino = s->st_ino;
  out->st_mode = s->st_mode;
  out->st_nlink = s->st_nlink;
  return 0;
}
int hb_target_fstat(int fd, struct hb_target_stat *out) {
  struct stat s;
  return fstat(fd, &s) ? -1 : cv(&s, out);
}
int hb_target_lstat(const char *p, struct hb_target_stat *out) {
  struct stat s;
  return lstat(p, &s) ? -1 : cv(&s, out);
}
