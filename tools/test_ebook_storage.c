/* Host-only syscall wrapping: every /contents operation is redirected to a
 * temporary fixture. */
#include "../runtime/apps/ebook/storage.h"
#include "../runtime/store/stock_fs_bridge.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static int fat = 1, low_space, fail_write, fail_sync;
static unsigned writes, created;
extern int __real_open(const char *, int, ...);
extern FILE *__real_fopen(const char *, const char *);
extern int __real_mkdir(const char *, mode_t);
extern int __real_unlink(const char *);
extern int __real_rename(const char *, const char *);
extern int __real_fsync(int);
extern ssize_t __real_write(int, const void *, size_t);
extern char *__real_realpath(const char *, char *);
static const char *root(void) {
  const char *p = getenv("ER_FIXTURE_ROOT");
  assert(p && p[0] == '/');
  return p;
}
static const char *tr(const char *p, char out[4096]) {
  if (!strcmp(p, "/contents") || !strncmp(p, "/contents/", 10)) {
    assert(!strstr(p, "/../"));
    assert(snprintf(out, 4096, "%s%s", root(), p + 9) < 4096);
    return out;
  }
  return p;
}
int __wrap_open(const char *p, int f, ...) {
  char b[4096];
  unsigned mode = 0;
  if (f & O_CREAT) {
    va_list a;
    va_start(a, f);
    mode = va_arg(a, unsigned);
    va_end(a);
    assert(!strcmp(p, "/contents/HOMEBREW/data/ebook/.pending"));
    created++;
  }
  return __real_open(tr(p, b), f, mode);
}
FILE *__wrap_fopen(const char *p, const char *m) {
  char b[4096];
  if (!strcmp(p, "/proc/mounts")) {
    snprintf(b, sizeof b, "%s/mounts.txt", root());
    return __real_fopen(b, m);
  }
  return __real_fopen(tr(p, b), m);
}
int __wrap_mkdir(const char *p, mode_t mode) {
  assert(!strcmp(p,"/contents/HOMEBREW/data")||!strcmp(p,"/contents/HOMEBREW/data/ebook")||!strcmp(p,"/contents/HOMEBREW/data/ebook/books"));
  char b[4096];
  return __real_mkdir(tr(p, b), mode);
}
int __wrap_unlink(const char *p) {
  char b[4096];
  return __real_unlink(tr(p, b));
}
int __wrap_rename(const char *a, const char *b) {
  char x[4096], y[4096];
  return __real_rename(tr(a, x), tr(b, y));
}
int __wrap_fsync(int fd) {
  if (fail_sync) {
    errno = EIO;
    return -1;
  }
  return __real_fsync(fd);
}
ssize_t __wrap_write(int fd, const void *p, size_t n) {
  if (fail_write) {
    errno = ENOSPC;
    return -1;
  }
  writes += (unsigned)n;
  return __real_write(fd, p, n);
}
char *__wrap_realpath(const char *p, char *out) {
  char path[4096], real[4096];
  if (!__real_realpath(tr(p, path), real))
    return 0;
  size_t n = strlen(root());
  if (!strncmp(real, root(), n) && (real[n] == '/' || !real[n])) {
    snprintf(out, 4096, "/contents%s", real + n);
    return out;
  }
  strcpy(out, real);
  return out;
}
static int cv(struct stat *s, struct hb_target_stat *out) {
  out->st_dev = s->st_dev;
  out->st_size = s->st_size;
  out->st_ino = s->st_ino;
  out->st_mode = s->st_mode;
  out->st_nlink = s->st_nlink;
  return 0;
}
int hb_target_lstat(const char *p, struct hb_target_stat *out) {
  char b[4096];
  struct stat s;
  if (lstat(tr(p, b), &s))
    return -1;
  return cv(&s, out);
}
static void put(unsigned char *p, unsigned n) {
  for (unsigned i = 0; i < 4; i++)
    p[i] = (unsigned char)(n >> (8 * i));
}
int __wrap_statfs(const char *p, void *out) {
  assert(!strcmp(p, "/contents"));
  unsigned char *b = out;
  memset(b, 0, 128);
  put(b, fat ? 0x4d44 : 0xef53);
  put(b + 4, 4096);
  put(b + 8, 100000);
  put(b + 12, 10000);
  put(b + 16, low_space ? 0 : 9000);
  return 0;
}
static void mounts(int right) {
  char p[4096];
  snprintf(p, sizeof p, "%s/mounts.txt", root());
  FILE *f = __real_fopen(p, "wb");
  assert(f);
  assert(fputs(right ? "/dev/mtdblock/2 /contents vfat rw 0 0\n"
                     : "/dev/mtdblock/0 /contents vfat rw 0 0\n",
               f) >= 0);
  assert(!fclose(f));
}
int main(void) {
  char p[4096], q[4096];
  snprintf(p, sizeof p, "%s/HOMEBREW", root());
  assert(!__real_mkdir(p, 0700));
  mounts(1);
  struct er_storage s, restored;
  assert(er_storage_open(&s) && s.ready);
  struct er_book b = {0};
  b.identity[0] = 0x55;
  b.bytes = 1000;
  b.current = 80;
  b.size = 20;
  b.requested = ER_UTF8;
  er_state_update(&s.state, &b, 0);
  assert(er_storage_save(&s) && s.state.sequence == 1 &&
         writes == ER_STATE_BYTES);
  assert(er_storage_open(&restored) && restored.state.sequence == 1);
  assert(er_state_find(&restored.state, b.identity)->offset == 80);
  b.current = 240;
  er_state_update(&s.state, &b, 2);
  fail_write = 1;
  assert(!er_storage_save(&s) && s.state.sequence == 1);
  fail_write = 0;
  fail_sync = 1;
  assert(!er_storage_save(&s) && s.state.sequence == 1);
  fail_sync = 0;
  assert(er_storage_open(&restored) &&
         er_state_find(&restored.state, b.identity)->offset == 80);
  assert(er_storage_save(&s) && s.state.sequence == 2);
  assert(er_storage_open(&restored) &&
         er_state_find(&restored.state, b.identity)->offset == 240);
  snprintf(p, sizeof p, "%s/HOMEBREW/data/ebook/progress.a", root());
  struct stat st;
  assert(!stat(p, &st) && st.st_size == ER_STATE_BYTES);
  snprintf(p, sizeof p, "%s/HOMEBREW/data/ebook/progress.b", root());
  FILE *f = __real_fopen(p, "wb");
  assert(f);
  fputs("xx", f);
  fclose(f);
  assert(er_storage_open(&restored) && restored.state.sequence == 1 &&
         er_state_find(&restored.state, b.identity)->offset == 80);
  unsigned before = writes, opens = created;
  low_space = 1;
  assert(!er_storage_save(&s));
  low_space = 0;
  fat = 0;
  assert(!er_storage_save(&s));
  fat = 1;
  mounts(0);
  assert(!er_storage_save(&s));
  assert(!er_storage_open(&restored));
  mounts(1);
  assert(writes == before && created == opens);
  snprintf(p, sizeof p, "%s/HOMEBREW/data/ebook", root());
  snprintf(q, sizeof q, "%s/HOMEBREW/data/ebook.original", root());
  assert(!__real_rename(p, q));
  assert(!symlink(q, p));
  assert(!er_storage_save(&s));
  assert(writes == before && created == opens);
  puts("EBook storage: exact bounded slots, progress restart, failed "
       "write/fsync, corrupt-newest recovery, "
       "low-space/wrong-mount/non-FAT/symlink denial passed; all I/O "
       "redirected to PC fixture");
  return 0;
}
