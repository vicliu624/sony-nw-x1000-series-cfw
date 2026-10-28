#include "storage.h"
#include "epub/epub.h"
#include "../../../sdk/include/x1000/services/stat.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
extern int er_sony_statfs(const char *, void *) __asm__("statfs");
extern int er_sscanf(const char *, const char *, ...) __asm__("sscanf");
static const char *data = "/contents/HOMEBREW/data/ebook";
static uint32_t get(const unsigned char *p) {
  return p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}
static void put(unsigned char *p, uint32_t v) {
  for (unsigned i = 0; i < 4; i++)
    p[i] = (unsigned char)(v >> (i * 8));
}
static unsigned state_hash(const unsigned char *p) {
  unsigned h = 2166136261u;
  for (unsigned i = 0; i < ER_STATE_BYTES; i++)
    h = (h ^ ((i >= 20 && i < 24) ? 0 : p[i])) * 16777619u;
  return h;
}
struct er_mark *er_state_find(struct er_state *s, const unsigned char key[32]) {
  for (unsigned i = 0; i < 128; i++)
    if (!memcmp(s->marks[i].key, key, 32))
      return s->marks + i;
  return 0;
}
int er_state_decode(struct er_state *s, const unsigned char *p, unsigned n) {
  if (n != ER_STATE_BYTES || (memcmp(p,"XREAD1\0\0",8)&&memcmp(p,"XREAD2\0\0",8)) || (get(p+8)!=1&&get(p+8)!=2) ||
      get(p + 16) >= 128 || get(p + 20) != state_hash(p))
    return 0;
  memset(s, 0, sizeof(*s));
  s->sequence = get(p + 12);
  s->cursor = get(p + 16);
  for (unsigned i = 0; i < 128; i++) {
    const unsigned char *r = p + 64 + i * 48;
    struct er_mark *m = s->marks + i;
    memcpy(m->key, r, 32);
    m->bytes = get(r + 32);
    m->offset = get(r + 36);
    m->size = r[40];
    m->theme = r[41];
    m->encoding = r[42];
    m->format=get(p+8)==2?r[43]:0;m->chapter=get(p+8)==2?get(r+44):0;
    if (m->bytes > 64 * 1024 * 1024 || (m->format?m->offset>EP_TOKENS:m->offset>m->bytes) || m->format>1 || m->chapter>=EP_SPINE || m->theme > 2 ||
        m->encoding > ER_UTF16BE ||
        (m->size && m->size != 16 && m->size != 20 && m->size != 24))
      return 0;
  }
  return 1;
}
void er_state_encode(const struct er_state *s,
                     unsigned char out[ER_STATE_BYTES]) {
  memset(out, 0, ER_STATE_BYTES);
  memcpy(out, "XREAD2\0\0", 8);
  put(out + 8, 2);
  put(out + 12, s->sequence);
  put(out + 16, s->cursor);
  for (unsigned i = 0; i < 128; i++) {
    const struct er_mark *m = s->marks + i;
    unsigned char *r = out + 64 + i * 48;
    memcpy(r, m->key, 32);
    put(r + 32, m->bytes);
    put(r + 36, m->offset);
    r[40] = (unsigned char)m->size;
    r[41] = (unsigned char)m->theme;
    r[42] = (unsigned char)m->encoding;
    r[43]=(unsigned char)m->format;put(r+44,m->chapter);
  }
  put(out + 20, state_hash(out));
}
void er_state_update(struct er_state *s, const struct er_book *b,
                     unsigned theme) {
  struct er_mark *m = er_state_find(s, b->identity);
  if (!m) {
    m = s->marks + s->cursor;
    s->cursor = (s->cursor + 1) % 128;
  }
  memcpy(m->key, b->identity, 32);
  m->bytes = b->bytes;
  m->offset = b->current;
  m->size = b->size;
  m->theme = theme;
  m->encoding = b->requested;
  m->format=b->epub?1:0;m->chapter=b->epub?b->epub->chapter:0;
}
static int safe_dir(const char *path, unsigned long long dev) {
  char resolved[4096];
  struct hb_target_stat s;
  return !hb_target_lstat(path, &s) && S_ISDIR(s.st_mode) && s.st_dev == dev &&
         realpath(path, resolved) && !strcmp(path, resolved);
}
static int volume(unsigned long long *dev, unsigned long long *available) {
  unsigned char fs[128] = {0};
  struct hb_target_stat s;
  char resolved[4096];
  if (hb_target_lstat("/contents", &s) || !S_ISDIR(s.st_mode) ||
      !realpath("/contents", resolved) || strcmp(resolved, "/contents") ||
      er_sony_statfs("/contents", fs) || get(fs) != 0x4d44 || !get(fs + 4) ||
      get(fs + 16) > get(fs + 12))
    return 0;
  FILE *f = fopen("/proc/mounts", "r");
  if (!f)
    return 0;
  char line[1024], source[128], mount[128], type[32];
  int ok = 0;
  while (fgets(line, sizeof line, f))
    if (er_sscanf(line, "%127s %127s %31s", source, mount, type) == 3 &&
        !strcmp(mount, "/contents") && !strcmp(type, "vfat") &&
        (!strcmp(source, "/dev/mtdblock/2") ||
         !strcmp(source, "/dev/mtdblock2")))
      ok = 1;
  fclose(f);
  if (!ok)
    return 0;
  *dev = s.st_dev;
  *available = (unsigned long long)get(fs + 4) * get(fs + 16);
  return 1;
}
static int regular(const char *path, unsigned long long dev) {
  struct hb_target_stat s;
  return !hb_target_lstat(path, &s) && S_ISREG(s.st_mode) && s.st_nlink == 1 &&
         s.st_dev == dev;
}
static int create_dir(const char *path, unsigned long long dev) {
  struct hb_target_stat s;
  if (hb_target_lstat(path, &s)) {
    if (errno != ENOENT || mkdir(path, 0700))
      return 0;
  }
  return safe_dir(path, dev);
}
static int load_slot(struct er_state *out, const char *path,
                     unsigned long long dev) {
  if (!regular(path, dev))
    return 0;
  int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
  if (fd < 0)
    return 0;
  unsigned char bytes[ER_STATE_BYTES + 1];
  unsigned used = 0;
  while (used < sizeof bytes) {
    ssize_t n = read(fd, bytes + used, sizeof bytes - used);
    if (n < 0 && errno == EINTR)
      continue;
    if (n < 0) {
      close(fd);
      return 0;
    }
    if (!n)
      break;
    used += (unsigned)n;
  }
  close(fd);
  return er_state_decode(out, bytes, used);
}
int er_storage_open(struct er_storage *s) {
  memset(s, 0, sizeof(*s));
  unsigned long long available;
  if (!volume(&s->device, &available))
    return 0;
  if (!safe_dir("/contents/HOMEBREW", s->device) ||
      !create_dir("/contents/HOMEBREW/data", s->device) ||
      !create_dir(data, s->device) ||
      !create_dir("/contents/HOMEBREW/data/ebook/books", s->device))
    return 0;
  struct er_state a, b;
  int aa = load_slot(&a, "/contents/HOMEBREW/data/ebook/progress.a", s->device),
      bb = load_slot(&b, "/contents/HOMEBREW/data/ebook/progress.b", s->device);
  if (aa && bb)
    s->state = (int32_t)(a.sequence - b.sequence) > 0 ? a : b;
  else if (aa)
    s->state = a;
  else if (bb)
    s->state = b;
  s->ready = 1;
  return 1;
}
int er_storage_save(struct er_storage *s) {
  unsigned long long dev, available;
  if (!s->ready || !volume(&dev, &available) || dev != s->device ||
      available < ER_STATE_BYTES + 65536 ||
      !safe_dir("/contents/HOMEBREW", dev) ||
      !safe_dir("/contents/HOMEBREW/data", dev) || !safe_dir(data, dev))
    return 0;
  const char *tmp = "/contents/HOMEBREW/data/ebook/.pending";
  uint32_t sequence = s->state.sequence + 1;
  const char *dest = sequence & 1 ? "/contents/HOMEBREW/data/ebook/progress.a"
                                  : "/contents/HOMEBREW/data/ebook/progress.b";
  struct hb_target_stat st;
  if (!hb_target_lstat(tmp, &st)) {
    if (!regular(tmp, dev) || unlink(tmp))
      return 0;
  } else if (errno != ENOENT)
    return 0;
  if (!hb_target_lstat(dest, &st)) {
    if (!regular(dest, dev))
      return 0;
  } else if (errno != ENOENT)
    return 0;
  unsigned char bytes[ER_STATE_BYTES];
  uint32_t old = s->state.sequence;
  s->state.sequence = sequence;
  er_state_encode(&s->state, bytes);
  s->state.sequence = old;
  int fd = open(tmp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  if (fd < 0)
    return 0;
  unsigned used = 0;
  int ok = 1;
  while (used < sizeof bytes) {
    ssize_t n = write(fd, bytes + used, sizeof bytes - used);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0) {
      ok = 0;
      break;
    }
    used += (unsigned)n;
  }
  if (fsync(fd))
    ok = 0;
  if (close(fd))
    ok = 0;
  if (ok && rename(tmp, dest) == 0) {
    int d = open(data, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    if (d < 0)
      return 0;
    ok = fsync(d) == 0;
    if (close(d))
      ok = 0;
    if (ok)
      s->state.sequence = sequence;
    return ok;
  }
  unlink(tmp);
  return 0;
}
int er_books_scan(struct er_item items[ER_MAX_BOOKS]) {
  struct hb_target_stat root;
  if (hb_target_lstat("/contents/HOMEBREW/data/ebook/books", &root) || !S_ISDIR(root.st_mode))
    return -1;
  char resolved[4096];
  if (!realpath("/contents/HOMEBREW/data/ebook/books", resolved) ||
      strcmp(resolved, "/contents/HOMEBREW/data/ebook/books"))
    return -1;
  DIR *d = opendir("/contents/HOMEBREW/data/ebook/books");
  if (!d)
    return -1;
  struct dirent *e;
  unsigned count = 0;
  while ((e = readdir(d)) && count < ER_MAX_BOOKS) {
    size_t n = strlen(e->d_name);
    if (n < 5 || n > 255 || e->d_name[0] == '.' || strchr(e->d_name, '/') ||
        strchr(e->d_name, '\\') || (strcasecmp(e->d_name+n-4,".txt")&&(n<6||strcasecmp(e->d_name+n-5,".epub"))))
      continue;
    char path[512];
    snprintf(path, sizeof path, "/contents/HOMEBREW/data/ebook/books/%s", e->d_name);
    struct hb_target_stat s;
    if (hb_target_lstat(path, &s) || !S_ISREG(s.st_mode) ||
        s.st_dev != root.st_dev || s.st_size < 0 ||
        s.st_size > 64 * 1024 * 1024)
      continue;
    strcpy(items[count].name, e->d_name);
    items[count].bytes = (uint32_t)s.st_size;
    count++;
  }
  closedir(d);
  for (unsigned i = 0; i < count; i++)
    for (unsigned j = i + 1; j < count; j++)
      if (strcmp(items[i].name, items[j].name) > 0) {
        struct er_item t = items[i];
        items[i] = items[j];
        items[j] = t;
      }
  return (int)count;
}
