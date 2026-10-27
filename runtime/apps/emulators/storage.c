/* Ordinary files on verified /contents VFAT only. Never mount or touch raw
 * flash. */
#include "platform.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <unistd.h>
// clang-format off
/* Must follow system declarations: maps the verified old Sony stat ABI. */
#include "../../store/target_abi.h"
// clang-format on
extern int es_sscanf(const char *, const char *, ...) __asm__("sscanf");
static char root[256];
static dev_t device;
static int ready;
int es_mount_matches(const char *s) {
  return !strcmp(s, "/dev/mtdblock/2 /contents vfat") ||
         !strcmp(s, "/dev/mtdblock2 /contents vfat");
}
const char *es_root(void) { return root; }
static int regular(const char *p) {
  struct stat st;
  return !lstat(p, &st) && S_ISREG(st.st_mode) && st.st_nlink == 1 &&
         st.st_dev == device;
}
static int live(void) {
  struct stat st;
  struct statfs fs;
  return ready && !lstat(root, &st) && S_ISDIR(st.st_mode) &&
         st.st_dev == device && !statfs(root, &fs) &&
         (unsigned long)fs.f_type == 0x4d44;
}
static int path(char *out, const char *name) {
  if (!live() || !name || !*name || strstr(name, "..") || name[0] == '/' ||
      strchr(name, '\\') || strlen(name) > 180)
    return 0;
  return snprintf(out, 512, "%s/%s", root, name) > 0;
}
int es_open(const char *id) {
  char expected[256], resolved[4096], line[1024], dev[128], mount[128],
      type[32], triple[300];
  struct stat st, contents;
  struct statfs fs;
  ready = 0;
  root[0] = 0;
  if (strcmp(id, "gbc") && strcmp(id, "tamagotchi-id"))
    return 0;
  snprintf(expected, sizeof expected, "/contents/HOMEBREW/apps/%s", id);
  if (!realpath(expected, resolved) || strlen(resolved) >= sizeof root ||
      strcmp(expected, resolved) || lstat(expected, &st) ||
      !S_ISDIR(st.st_mode) || lstat("/contents", &contents) ||
      contents.st_dev != st.st_dev || statfs(expected, &fs) ||
      (unsigned long)fs.f_type != 0x4d44)
    return 0;
  FILE *f = fopen("/proc/mounts", "r");
  if (!f)
    return 0;
  int found = 0;
  while (fgets(line, sizeof line, f))
    if (es_sscanf(line, "%127s %127s %31s", dev, mount, type) == 3) {
      snprintf(triple, sizeof triple, "%s %s %s", dev, mount, type);
      if (es_mount_matches(triple))
        found = 1;
    }
  fclose(f);
  if (!found)
    return 0;
  device = st.st_dev;
  char parent[256];
  snprintf(parent, sizeof parent, "/contents/HOMEBREW/data");
  if (lstat(parent, &st)) {
    if (errno != ENOENT || mkdir(parent, 0700))
      return 0;
  }
  if (lstat(parent, &st) || !S_ISDIR(st.st_mode) || st.st_dev != device ||
      !realpath(parent, resolved) || strcmp(parent, resolved))
    return 0;
  snprintf(expected, sizeof expected, "/contents/HOMEBREW/data/%s", id);
  if (lstat(expected, &st)) {
    if (errno != ENOENT || mkdir(expected, 0700))
      return 0;
  }
  if (lstat(expected, &st) || !S_ISDIR(st.st_mode) || st.st_dev != device ||
      !realpath(expected, resolved) || strcmp(expected, resolved))
    return 0;
  strcpy(root, expected);
  ready = 1;
  char p[512];
  for (unsigned i = 0; i < 2; i++) {
    snprintf(p, sizeof p, "%s/%s", root, i ? "saves" : "roms");
    if (lstat(p, &st)) {
      if (errno != ENOENT || mkdir(p, 0700))
        return ready = 0;
    }
    if (lstat(p, &st) || !S_ISDIR(st.st_mode) || st.st_dev != device)
      return ready = 0;
  }
  return 1;
}
int es_read(const char *name, void *buf, unsigned size, unsigned off) {
  char p[512];
  if (!path(p, name))
    return -1;
  struct stat st;
  if (lstat(p, &st))
    return errno == ENOENT ? 0 : -1;
  if (!regular(p))
    return -1;
  FILE *f = fopen(p, "rb");
  if (!f)
    return -1;
  if (fseek(f, (long)off, SEEK_SET)) {
    fclose(f);
    return -1;
  }
  size_t n = fread(buf, 1, size, f);
  int failed = ferror(f);
  if (fclose(f))
    failed = 1;
  return failed ? -1 : (int)n;
}
static int all(int fd, const void *p, unsigned n) {
  while (n) {
    ssize_t r = write(fd, p, n > 16384 ? 16384 : n);
    if (r < 0 && errno == EINTR)
      continue;
    if (r <= 0)
      return 0;
    p = (const char *)p + r;
    n -= (unsigned)r;
  }
  return 1;
}
int es_write(const char *name, const void *a, unsigned an, const void *b,
             unsigned bn) {
  char dest[512], tmp[512], dir[512];
  struct stat st;
  struct statfs fs;
  if (!path(dest, name) || strchr(name, '/') != strrchr(name, '/') ||
      strncmp(name, "saves/", 6))
    return 0;
  snprintf(tmp, sizeof tmp, "%s/saves/.pending", root);
  snprintf(dir, sizeof dir, "%s/saves", root);
  if (lstat(dir, &st) || !S_ISDIR(st.st_mode) || st.st_dev != device ||
      statfs(dir, &fs) || (unsigned long)fs.f_type != 0x4d44 || !fs.f_bsize ||
      (unsigned long long)fs.f_bavail * (unsigned)fs.f_bsize <
          (unsigned long long)an + bn + 131072)
    return 0;
  if (!lstat(dest, &st) && !regular(dest))
    return 0;
  if (!lstat(tmp, &st)) {
    if (!regular(tmp) || unlink(tmp))
      return 0;
  } else if (errno != ENOENT)
    return 0;
  int fd = open(tmp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  if (fd < 0)
    return 0;
  int ok = all(fd, a, an) && all(fd, b, bn);
  if (fsync(fd))
    ok = 0;
  if (close(fd))
    ok = 0;
  if (ok && live() && rename(tmp, dest) == 0) {
    fd = open(dir, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    if (fd < 0)
      return 0;
    ok = fsync(fd) == 0;
    if (close(fd))
      ok = 0;
    return ok;
  }
  unlink(tmp);
  return 0;
}
int es_remove(const char *name) {
  char p[512];
  if (strncmp(name, "saves/", 6) || !path(p, name))
    return 0;
  if (!regular(p))
    return access(p, F_OK) < 0 && errno == ENOENT;
  return unlink(p) == 0;
}
int es_move(const char *a, const char *b) {
  char x[512], y[512];
  if (strncmp(a, "saves/", 6) || strncmp(b, "saves/", 6) || !path(x, a) ||
      !path(y, b))
    return 0;
  if (!regular(x))
    return access(x, F_OK) < 0 && errno == ENOENT;
  struct stat st;
  if (!lstat(y, &st) && !regular(y))
    return 0;
  return rename(x, y) == 0;
}
int es_rom_list(char names[64][128]) {
  char dir[512];
  if (!path(dir, "roms"))
    return -1;
  DIR *d = opendir(dir);
  if (!d)
    return -1;
  struct dirent *e;
  unsigned n = 0;
  while ((e = readdir(d)) && n < 64) {
    size_t len = strlen(e->d_name);
    if (!len || len >= 128 || e->d_name[0] == '.' || strchr(e->d_name, '/') ||
        strchr(e->d_name, '\\'))
      continue;
    if (len < 3 || (strcasecmp(e->d_name + len - 3, ".gb") &&
                    (len < 4 || strcasecmp(e->d_name + len - 4, ".gbc"))))
      continue;
    char p[512];
    if (snprintf(p, sizeof p, "%s/%s", dir, e->d_name) >= (int)sizeof p ||
        !regular(p))
      continue;
    strcpy(names[n++], e->d_name);
  }
  closedir(d);
  for (unsigned i = 0; i < n; i++)
    for (unsigned j = i + 1; j < n; j++)
      if (strcmp(names[i], names[j]) > 0) {
        char tmp[128];
        strcpy(tmp, names[i]);
        strcpy(names[i], names[j]);
        strcpy(names[j], tmp);
      }
  return (int)n;
}
