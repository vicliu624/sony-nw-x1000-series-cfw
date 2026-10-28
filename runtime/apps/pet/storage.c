#include "storage.h"
#include "../../../sdk/include/x1000/services/stat.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
extern int pet_statfs(const char *, void *) __asm__("statfs");
extern int pet_scan(const char *, const char *, ...) __asm__("sscanf");
static unsigned get(const unsigned char *p) {
  return p[0] | (unsigned)p[1] << 8 | (unsigned)p[2] << 16 |
         (unsigned)p[3] << 24;
}
static int mount_ok(void) {
  FILE *f = fopen("/proc/mounts", "r");
  if (!f)
    return 0;
  char line[1024], dev[128], path[256], type[32], opts[256];
  int count = 0, bad = 0;
  while (fgets(line, sizeof line, f)) {
    if (pet_scan(line, "%127s %255s %31s %255s", dev, path, type, opts) != 4) {
      bad = 1;
      break;
    }
    if (!strcmp(path, "/contents")) {
      count++;
      if (strcmp(dev, "/dev/mtdblock/2") || strcmp(type, "vfat"))
        bad = 1;
      char *p = opts;
      unsigned rw = 0;
      while (*p) {
        char *end = strchr(p, ',');
        unsigned n = end ? (unsigned)(end - p) : (unsigned)strlen(p);
        if (n == 2 && !memcmp(p, "ro", 2))
          bad = 1;
        if (n == 2 && !memcmp(p, "rw", 2))
          rw++;
        if (!end)
          break;
        p = end + 1;
      }
      if (rw != 1)
        bad = 1;
    } else if (!strncmp(path, "/contents/", 10))
      bad = 1;
  }
  if (ferror(f))
    bad = 1;
  if (fclose(f))
    bad = 1;
  return count == 1 && !bad;
}
static int path(struct pet_storage *s, const char *name, char out[128]) {
  int n = snprintf(out, 128, "/proc/self/fd/%d/%s", s->fd, name);
  return n > 0 && n < 128;
}
static int current(struct pet_storage *s) {
  struct hb_target_stat a, b;
  return s->fd >= 0 && mount_ok() &&
         !hb_target_lstat("/contents/HOMEBREW/data/pet", &a) &&
         !hb_target_fstat(s->fd, &b) && S_ISDIR(a.st_mode) &&
         a.st_dev == s->device && b.st_dev == s->device &&
         a.st_ino == s->inode && b.st_ino == s->inode;
}
static int regular(struct pet_storage *s, const char *name, int absent) {
  char p[128];
  struct hb_target_stat st;
  if (!path(s, name, p))
    return 0;
  if (hb_target_lstat(p, &st))
    return absent && errno == ENOENT;
  return S_ISREG(st.st_mode) && st.st_nlink == 1 && st.st_dev == s->device &&
         st.st_size >= 0 && st.st_size <= 48;
}
static unsigned checksum(const unsigned char *p) {
  unsigned h = 2166136261u;
  for (unsigned i = 0; i < 44; i++)
    h = (h ^ p[i]) * 16777619u;
  return h;
}
static void put(unsigned char *b, unsigned n) {
  for (unsigned i = 0; i < 4; i++)
    b[i] = (unsigned char)(n >> (8 * i));
}
static int load(struct pet_storage *s, int slot, struct pet_state *state,
                unsigned *generation) {
  char name[16], p[128];
  snprintf(name, sizeof name, "state-%d.bin", slot);
  if (!regular(s, name, 0) || !path(s, name, p))
    return 0;
  int fd = open(p, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
  if (fd < 0)
    return 0;
  struct hb_target_stat st;
  unsigned char b[49];
  unsigned used = 0;
  int ok = !hb_target_fstat(fd, &st) && S_ISREG(st.st_mode) &&
           st.st_nlink == 1 && st.st_dev == s->device && st.st_size == 48;
  while (ok && used < sizeof b) {
    ssize_t n = read(fd, b + used, sizeof b - used);
    if (n < 0 && errno == EINTR)
      continue;
    if (n < 0) {
      ok = 0;
      break;
    }
    if (!n)
      break;
    used += (unsigned)n;
  }
  if (close(fd))
    ok = 0;
  if (!ok || used != 48 || get(b + 44) != checksum(b) ||
      !pet_decode(state, b, 40))
    return 0;
  *generation = get(b + 40);
  return 1;
}
void pet_storage_close(struct pet_storage *s) {
  if (s->fd >= 0)
    close(s->fd);
  s->fd = -1;
}
int pet_storage_open(struct pet_storage *s, struct pet_state *out) {
  memset(s, 0, sizeof *s);
  s->fd = -1;
  s->slot = -1;
  if (!mount_ok())
    return -1;
  struct hb_target_stat root, vol, st;
  if (hb_target_lstat("/", &root) || hb_target_lstat("/contents", &vol) ||
      !S_ISDIR(vol.st_mode) || root.st_dev == vol.st_dev)
    return -1;
  int fd = open("/contents", O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
  if (fd < 0)
    return -1;
  const char *names[] = {"HOMEBREW", "data", "pet"};
  for (unsigned i = 0; i < 3; i++) {
    char p[128];
    snprintf(p, sizeof p, "/proc/self/fd/%d/%s", fd, names[i]);
    int next = open(p, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    if (next < 0 && errno == ENOENT && i > 0) {
      if (mkdir(p, 0700)) {
        close(fd);
        return -1;
      }
      next = open(p, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    }
    if (next < 0 || hb_target_fstat(next, &st) || !S_ISDIR(st.st_mode) ||
        st.st_dev != vol.st_dev) {
      if (next >= 0)
        close(next);
      close(fd);
      return -1;
    }
    close(fd);
    fd = next;
  }
  s->fd = fd;
  s->device = st.st_dev;
  s->inode = st.st_ino;
  if (!current(s)) {
    pet_storage_close(s);
    return -1;
  }
  struct pet_state a, b;
  unsigned ga = 0, gb = 0;
  int aa = load(s, 0, &a, &ga), bb = load(s, 1, &b, &gb);
  if (aa && (!bb || (ga != gb && (ga - gb) < 0x80000000u))) {
    *out = a;
    s->slot = 0;
    s->generation = ga;
    return 1;
  }
  if (bb) {
    *out = b;
    s->slot = 1;
    s->generation = gb;
    return 1;
  }
  char p[128];
  struct hb_target_stat file;
  path(s, "state-0.bin", p);
  int exists = !hb_target_lstat(p, &file);
  path(s, "state-1.bin", p);
  exists |= !hb_target_lstat(p, &file);
  return exists ? -2 : 0;
}
int pet_storage_save(struct pet_storage *s, const struct pet_state *state,
                     volatile int *stop) {
  if (s->fd < 0 && !*stop) {
    struct pet_state ignored;
    if (pet_storage_open(s, &ignored) == -1)
      return 0;
  }
  if (*stop || !current(s))
    return 0;
  unsigned char fs[128] = {0};
  if (pet_statfs("/contents", fs) || get(fs) != 0x4d44 || get(fs + 4) < 512 ||
      get(fs + 4) > 1048576 || get(fs + 16) < 128)
    return 0;
  int slot = s->slot == 0 ? 1 : 0;
  char name[16], temp[128], dest[128];
  snprintf(name, sizeof name, "state-%d.bin", slot);
  if (!regular(s, name, 1) || !regular(s, "state.tmp", 1) ||
      !path(s, "state.tmp", temp) || !path(s, name, dest))
    return 0;
  if (unlink(temp) && errno != ENOENT)
    return 0;
  int fd = open(temp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  if (fd < 0)
    return 0;
  struct hb_target_stat st;
  int ok = !hb_target_fstat(fd, &st) && S_ISREG(st.st_mode) &&
           st.st_nlink == 1 && st.st_dev == s->device;
  unsigned char b[48];
  pet_encode(state, b);
  put(b + 40, s->generation + 1);
  put(b + 44, checksum(b));
  unsigned used = 0;
  while (ok && used < sizeof b && !*stop) {
    ssize_t n = write(fd, b + used, sizeof b - used);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0) {
      ok = 0;
      break;
    }
    used += (unsigned)n;
  }
  if (used != sizeof b || *stop || fsync(fd))
    ok = 0;
  if (close(fd))
    ok = 0;
  if (!ok || *stop || !current(s) || !regular(s, name, 1) || rename(temp, dest))
    return 0;
  if (fsync(s->fd))
    return 0;
  s->slot = slot;
  s->generation++;
  return 1;
}
