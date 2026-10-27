#include "dictionary.h"
#include "../../store/stock_fs_bridge.h"
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static unsigned le32(const unsigned char *p) {
  return p[0] | ((unsigned)p[1] << 8) | ((unsigned)p[2] << 16) |
         ((unsigned)p[3] << 24);
}
static unsigned le16(const unsigned char *p) {
  return p[0] | ((unsigned)p[1] << 8);
}
static FILE *readonly(const char *path, unsigned limit, unsigned *size) {
  int fd = open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW);
  if (fd < 0)
    return 0;
  struct hb_target_stat s;
  if (hb_target_fstat(fd, &s) || !S_ISREG(s.st_mode) || s.st_size < 0 ||
      (unsigned long long)s.st_size > limit) {
    close(fd);
    return 0;
  }
  FILE *f = fdopen(fd, "rb");
  if (!f) {
    close(fd);
    return 0;
  }
  *size = (unsigned)s.st_size;
  return f;
}
int dx_open(struct dx *d, const char *path) {
  memset(d, 0, sizeof(*d));
  unsigned char h[64];
  d->file = readonly(path, 128 * 1024 * 1024, &d->bytes);
  if (!d->file)
    return 0;
  if (fread(h, 1, sizeof h, d->file) != sizeof h ||
      memcmp(h, "XDICT1\0\0", 8) || le32(h + 8) != 1 || le32(h + 16) != 16 ||
      le32(h + 20) != 64)
    goto fail;
  d->count = le32(h + 12);
  d->payload = le32(h + 24);
  if (!d->count || d->count > 2000000 || d->payload != 64 + d->count * 16 ||
      d->payload > d->bytes || le32(h + 28) != d->bytes)
    goto fail;
  return 1;
fail:
  dx_close(d);
  return 0;
}
void dx_close(struct dx *d) {
  if (d->file)
    fclose(d->file);
  memset(d, 0, sizeof(*d));
}
static int entry(struct dx *d, unsigned n, unsigned *ko, unsigned *kn,
                 unsigned *to, unsigned *tn) {
  unsigned char r[16];
  if (!d->file || n >= d->count ||
      fseek(d->file, (long)(64 + n * 16), SEEK_SET) ||
      fread(r, 1, 16, d->file) != 16)
    return 0;
  *ko = le32(r);
  *kn = le16(r + 4);
  *to = le32(r + 8);
  *tn = le32(r + 12);
  return *kn && *kn < 64 && *tn && *tn <= 65535 && *ko >= d->payload &&
         *ko <= d->bytes && *kn <= d->bytes - *ko && *to >= *ko + *kn &&
         *to <= d->bytes && *tn <= d->bytes - *to;
}
int dx_word(struct dx *d, uint32_t n, char out[64]) {
  unsigned ko, kn, to, tn;
  if (!entry(d, n, &ko, &kn, &to, &tn) || fseek(d->file, (long)ko, SEEK_SET) ||
      fread(out, 1, kn, d->file) != kn)
    return 0;
  out[kn] = 0;
  for (unsigned i = 0; i < kn; i++)
    if ((unsigned char)out[i] < 32 || (unsigned char)out[i] > 126)
      return 0;
  return 1;
}
int dx_lower(struct dx *d, const char *query, uint32_t *out) {
  char q[64], word[64];
  unsigned len = (unsigned)strlen(query);
  if (len > 63 || !d->file)
    return 0;
  for (unsigned i = 0; i <= len; i++) {
    unsigned char c = query[i];
    if (c >= 'A' && c <= 'Z')
      c += 32;
    if (c > 126 || (c && c < 32))
      return 0;
    q[i] = (char)c;
  }
  uint32_t lo = 0, hi = d->count;
  while (lo < hi) {
    uint32_t mid = lo + (hi - lo) / 2;
    if (!dx_word(d, mid, word))
      return 0;
    if (strcmp(word, q) < 0)
      lo = mid + 1;
    else
      hi = mid;
  }
  *out = lo;
  return 1;
}
int dx_text(struct dx *d, uint32_t n, char *out, unsigned cap) {
  unsigned ko, kn, to, tn;
  if (!entry(d, n, &ko, &kn, &to, &tn) || tn >= cap ||
      fseek(d->file, (long)to, SEEK_SET) || fread(out, 1, tn, d->file) != tn)
    return 0;
  out[tn] = 0;
  if (memchr(out, 0, tn))
    return 0;
  return (int)tn;
}
int dx_font_open(struct dx_font *f, const char *path) {
  unsigned size;
  memset(f, 0, sizeof(*f));
  FILE *p = readonly(path, 2162704, &size);
  if (!p)
    return 0;
  if (size != 2162704) {
    fclose(p);
    return 0;
  }
  f->data = malloc(size);
  int ok = f->data && fread(f->data, 1, size, p) == size &&
           !memcmp(f->data, "XFONT1\0\0", 8) && le32(f->data + 8) == 65536 &&
           le32(f->data + 12) == 16;
  fclose(p);
  if (!ok) {
    dx_font_close(f);
    return 0;
  }
  for (unsigned i = 0; i < 65536; i++)
    if (f->data[16 + i] != 0 && f->data[16 + i] != 8 && f->data[16 + i] != 16) {
      dx_font_close(f);
      return 0;
    }
  return 1;
}
void dx_font_close(struct dx_font *f) {
  free(f->data);
  f->data = 0;
}
unsigned dx_utf8(const char **s) {
  const unsigned char *p = (const unsigned char *)*s;
  unsigned cp = *p, n;
  if (!cp)
    return 0;
  if (cp < 128) {
    *s += 1;
    return cp;
  }
  if (cp >= 0xc2 && cp <= 0xdf) {
    cp &= 31;
    n = 2;
  } else if (cp >= 0xe0 && cp <= 0xef) {
    cp &= 15;
    n = 3;
  } else if (cp >= 0xf0 && cp <= 0xf4) {
    cp &= 7;
    n = 4;
  } else {
    *s += 1;
    return 0xfffd;
  }
  for (unsigned i = 1; i < n; i++) {
    if (!p[i] || (p[i] & 0xc0) != 0x80) {
      *s += 1;
      return 0xfffd;
    }
    cp = (cp << 6) | (p[i] & 63);
  }
  if ((n == 3 && cp < 0x800) || (n == 4 && cp < 0x10000) || cp > 0x10ffff ||
      (cp >= 0xd800 && cp <= 0xdfff)) {
    *s += 1;
    return 0xfffd;
  }
  *s += n;
  return cp;
}
unsigned dx_width(const struct dx_font *f, unsigned cp) {
  if (cp > 65535)
    cp = 0xfffd;
  return f->data && f->data[16 + cp] ? f->data[16 + cp] : cp < 128 ? 8 : 16;
}
void dx_draw(const struct dx_font *f, uint16_t *pixels, int x, int y,
             const char *s, uint16_t color) {
  while (*s) {
    unsigned cp = dx_utf8(&s);
    if (cp > 65535)
      cp = 0xfffd;
    unsigned w = dx_width(f, cp);
    if (x + (int)w > 236)
      break;
    const unsigned char *b =
        f->data && f->data[16 + cp] ? f->data + 16 + 65536 + cp * 32 : 0;
    for (int j = 0; j < 16; j++)
      for (unsigned i = 0; i < w; i++) {
        int set = b ? !!((b[j * 2] << 8 | b[j * 2 + 1]) & (0x8000u >> i))
                    : (j == 0 || j == 15 || i == 0 || i == w - 1);
        if (set && x + (int)i >= 0 && x + (int)i < 240 && y + j >= 0 &&
            y + j < 432)
          pixels[(y + j) * 240 + x + i] = color;
      }
    x += (int)w;
  }
}
