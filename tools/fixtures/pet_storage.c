#define _GNU_SOURCE
#include "../../runtime/apps/pet/storage.h"
#include "../../runtime/store/stock_fs_bridge.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static char root[256];
static int mount_bad, low_space, fail_write, fail_sync, fail_rename;
static const char *mapped(const char *p, char b[512]) {
  if (!strncmp(p, "/contents", 9)) {
    snprintf(b, 512, "%s%s", root, p + 9);
    return b;
  }
  return p;
}
extern int __real_open(const char *, int, ...);
int __wrap_open(const char *p, int f, ...) {
  mode_t m = 0;
  if (f & O_CREAT) {
    va_list a;
    va_start(a, f);
    m = (mode_t)va_arg(a, int);
    va_end(a);
  }
  char b[512];
  return __real_open(mapped(p, b), f, m);
}
FILE *__real_fopen(const char *, const char *);
FILE *__wrap_fopen(const char *p, const char *m) {
  if (!strcmp(p, "/proc/mounts")) {
    FILE *f = tmpfile();
    assert(f);
    fprintf(f,
            "rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat %s 0 0\n",
            mount_bad ? "ro" : "rw");
    rewind(f);
    return f;
  }
  return __real_fopen(p, m);
}
static void convert(struct hb_target_stat *out, struct stat *s) {
  out->st_dev = s->st_dev;
  out->st_ino = s->st_ino;
  out->st_size = s->st_size;
  out->st_nlink = s->st_nlink;
  out->st_mode = s->st_mode;
}
int hb_target_lstat(const char *p, struct hb_target_stat *out) {
  char b[512];
  struct stat s;
  if (lstat(mapped(p, b), &s))
    return -1;
  convert(out, &s);
  return 0;
}
int hb_target_fstat(int fd, struct hb_target_stat *out) {
  struct stat s;
  if (fstat(fd, &s))
    return -1;
  convert(out, &s);
  return 0;
}
int __wrap_statfs(const char *p, void *out) {
  assert(!strcmp(p, "/contents"));
  unsigned *v = out;
  memset(out, 0, 128);
  v[0] = 0x4d44;
  v[1] = 4096;
  v[4] = low_space ? 0 : 1000;
  return 0;
}
ssize_t __real_write(int, const void *, size_t);
ssize_t __wrap_write(int fd, const void *p, size_t n) {
  if (fail_write) {
    errno = ENOSPC;
    return -1;
  }
  return __real_write(fd, p, n);
}
int __real_fsync(int);
int __wrap_fsync(int fd) {
  if (fail_sync) {
    errno = EIO;
    return -1;
  }
  return __real_fsync(fd);
}
int __real_rename(const char *, const char *);
int __wrap_rename(const char *a, const char *b) {
  if (fail_rename) {
    errno = EIO;
    return -1;
  }
  return __real_rename(a, b);
}
static void remove_file(const char *name) {
  char p[512];
  snprintf(p, sizeof p, "%s/HOMEBREW/data/pet/%s", root, name);
  assert(!unlink(p) || errno == ENOENT);
}
int main(void) {
  strcpy(root, "/dev/shm/x1000-pet-XXXXXX");
  assert(mkdtemp(root));
  char dir[512];
  snprintf(dir, sizeof dir, "%s/HOMEBREW", root);
  assert(!mkdir(dir, 0700));
  struct pet_session pet;
  pet_init(&pet);
  struct pet_storage s;
  volatile int stop = 0;
  assert(pet_storage_open(&s, &pet.state) == 0);
  assert(pet_storage_save(&s, &pet.state, &stop));
  pet_act(&pet, PET_PLAY);
  assert(pet_storage_save(&s, &pet.state, &stop));
  pet_storage_close(&s);
  struct pet_state loaded;
  assert(pet_storage_open(&s, &loaded) == 1 && loaded.joy == 85);
  unsigned char pair_bytes[125] = {0}, read_pair[4220];
  memcpy(pair_bytes, "PETPAIR1", 8);
  snprintf(dir, sizeof dir, "%s/HOMEBREW/data/pet/link.pair", root);
  FILE *pair_file = fopen(dir, "wb");
  assert(pair_file &&
         fwrite(pair_bytes, 1, sizeof pair_bytes, pair_file) ==
             sizeof pair_bytes &&
         !fclose(pair_file));
  assert(pet_storage_read_pair(&s, read_pair, sizeof read_pair) == 125);
  stop = 1;
  assert(!pet_storage_forget_pair(&s, &stop));
  stop = 0;
  assert(pet_storage_forget_pair(&s, &stop));
  assert(pet_storage_read_pair(&s, read_pair, sizeof read_pair) == 0);
  assert(!symlink("/etc/passwd", dir));
  assert(pet_storage_read_pair(&s, read_pair, sizeof read_pair) == -1);
  assert(!pet_storage_forget_pair(&s, &stop));
  remove_file("link.pair");
  pet_storage_close(&s);
  /* Corrupt newest snapshot; the older complete snapshot survives. */
  snprintf(dir, sizeof dir, "%s/HOMEBREW/data/pet/state-1.bin", root);
  FILE *f = fopen(dir, "wb");
  assert(f);
  fputs("broken", f);
  assert(!fclose(f));
  assert(pet_storage_open(&s, &loaded) == 1 && loaded.joy == 70);
  int *faults[] = {&low_space, &fail_write, &fail_sync, &fail_rename,
                   &mount_bad};
  for (unsigned i = 0; i < 5; i++) {
    *faults[i] = 1;
    assert(!pet_storage_save(&s, &pet.state, &stop));
    *faults[i] = 0;
    pet_storage_close(&s);
    assert(pet_storage_open(&s, &loaded) == 1 && loaded.joy == 70);
  }
  stop = 1;
  assert(!pet_storage_save(&s, &pet.state, &stop));
  stop = 0;
  assert(pet_storage_save(&s, &pet.state, &stop));
  pet_storage_close(&s);
  assert(pet_storage_open(&s, &loaded) == 1 && loaded.joy == 85);
  pet_storage_close(&s);
  remove_file("state-0.bin");
  remove_file("state-1.bin");
  remove_file("state.tmp");
  snprintf(dir, sizeof dir, "%s/HOMEBREW/data/pet/state-0.bin", root);
  assert(!symlink("/etc/passwd", dir));
  assert(pet_storage_open(&s, &loaded) == -2);
  assert(!pet_storage_save(&s, &pet.state, &stop));
  pet_storage_close(&s);
  remove_file("state-0.bin");
  mount_bad = 1;
  assert(pet_storage_open(&s, &loaded) == -1);
  mount_bad = 0;
  snprintf(dir, sizeof dir, "%s/HOMEBREW/data/pet", root);
  assert(!rmdir(dir));
  snprintf(dir, sizeof dir, "%s/HOMEBREW/data", root);
  assert(!rmdir(dir));
  snprintf(dir, sizeof dir, "%s/HOMEBREW", root);
  assert(!rmdir(dir));
  assert(!rmdir(root));
  puts("Pet storage: reload, corruption rollback, "
       "space/write/sync/rename/mount/stop/symlink cases passed");
  return 0;
}
