/* XFONT1 is the existing dictionary/reader bitmap format (GNU Unifont).
 * Decode policy follows dictionary.c, with bounded glyph caching instead of
 * loading the complete font. All rendering is clipped to the 240x432 canvas. */
#include "text.h"
#include "../../native/font.inc"
#include <string.h>
typedef char
    pet_font_cache_is_bounded[(sizeof(struct pet_font) <= 3072) ? 1 : -1];
int pet_font_open(struct pet_font *f, const char *path) {
  memset(f, 0, sizeof *f);
  FILE *p = fopen(path, "rb");
  if (!p)
    return 0;
  unsigned char h[16];
  int ok = !fseek(p, 0, SEEK_END) && ftell(p) == 2162704 &&
           !fseek(p, 0, SEEK_SET) && fread(h, 1, 16, p) == 16 &&
           !memcmp(h, "XFONT1\0\0", 8) && h[8] == 0 && h[9] == 0 &&
           h[10] == 1 && h[11] == 0 && h[12] == 16 && !h[13] && !h[14] &&
           !h[15];
  if (!ok) {
    fclose(p);
    return 0;
  }
  f->file = p;
  return 1;
}
void pet_font_close(struct pet_font *f) {
  if (f && f->file)
    fclose(f->file);
  if (f)
    memset(f, 0, sizeof *f);
}
unsigned pet_utf8(const char **s) {
  const unsigned char *p = (const unsigned char *)*s;
  unsigned cp = *p, n;
  if (!cp)
    return 0;
  if (cp < 128) {
    (*s)++;
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
    (*s)++;
    return 0xfffd;
  }
  for (unsigned i = 1; i < n; i++) {
    if (!p[i] || (p[i] & 0xc0) != 0x80) {
      (*s)++;
      return 0xfffd;
    }
    cp = (cp << 6) | (p[i] & 63);
  }
  if ((n == 3 && cp < 0x800) || (n == 4 && cp < 0x10000) || cp > 0x10ffff ||
      (cp >= 0xd800 && cp <= 0xdfff)) {
    (*s)++;
    return 0xfffd;
  }
  *s += n;
  return cp;
}
static struct pet_glyph *lookup(struct pet_font *f, unsigned cp) {
  if (!f || !f->file)
    return 0;
  if (cp > 65535)
    cp = 0xfffd;
  for (unsigned i = 0; i < 64; i++)
    if (f->cache[i].valid && f->cache[i].cp == cp)
      return &f->cache[i];
  struct pet_glyph *g = &f->cache[f->next++ % 64];
  memset(g, 0, sizeof *g);
  unsigned char width;
  if (fseek(f->file, (long)(16 + cp), SEEK_SET) ||
      fread(&width, 1, 1, f->file) != 1 || (width != 8 && width != 16))
    return 0;
  if (fseek(f->file, (long)(16 + 65536 + cp * 32), SEEK_SET) ||
      fread(g->bits, 1, 32, f->file) != 32)
    return 0;
  g->cp = cp;
  g->width = width;
  g->valid = 1;
  return g;
}
static unsigned width(struct pet_font *f, unsigned cp) {
  struct pet_glyph *g = lookup(f, cp);
  return g ? g->width : cp < 128 ? 8 : 16;
}
unsigned pet_text_width(struct pet_font *f, const char *s) {
  unsigned n = 0;
  while (*s && n < 65536) {
    unsigned cp = pet_utf8(&s);
    if (cp == '\n')
      break;
    n += width(f, cp);
  }
  return n;
}
static void pixel(unsigned short *p, int x, int y, unsigned short c) {
  if (x >= 0 && x < 240 && y >= 0 && y < 432)
    p[y * 240 + x] = c;
}
struct pet_text_result pet_text(struct pet_font *f, unsigned short *pixels,
                                int x, int y, unsigned maxw, unsigned maxlines,
                                const char *s, unsigned short color) {
  struct pet_text_result r = {0, 0, 0, 0};
  if (!pixels || !s || !maxlines || !maxw || x < 0 || x >= 240 || y < 0 ||
      y >= 432)
    return r;
  if (y + 16 > 432) {
    r.truncated = !!*s;
    return r;
  }
  if (maxw > (unsigned)(240 - x))
    maxw = (unsigned)(240 - x);
  const char *start = s;
  unsigned used = 0, line = 0;
  while (*s) {
    const char *before = s;
    unsigned cp = pet_utf8(&s);
    if (cp == '\r')
      continue;
    unsigned w = cp == '\n' ? 0 : width(f, cp);
    if (cp == '\n' || used + w > maxw) {
      line++;
      used = 0;
      if (line >= maxlines || y + (int)line * 18 + 16 > 432) {
        line--;
        s = before;
        r.truncated = 1;
        break;
      }
      if (cp == '\n')
        continue;
    }
    if (w > maxw) {
      s = before;
      r.truncated = 1;
      break;
    }
    struct pet_glyph *g = lookup(f, cp);
    if ((!g && cp != ' ') || cp > 65535 || cp == 0xfffd)
      r.missing++;
    for (unsigned j = 0; j < 16; j++)
      for (unsigned i = 0; i < w; i++) {
        int set = g ? !!(((unsigned)g->bits[j * 2] << 8 | g->bits[j * 2 + 1]) &
                         (0x8000u >> i))
                    : 0;
        if (!g && cp != ' ') {
          int n = cp >= 'A' && cp <= 'Z'   ? (int)cp - 'A' + 10
                  : cp >= 'a' && cp <= 'z' ? (int)cp - 'a' + 10
                  : cp >= '0' && cp <= '9' ? (int)cp - '0'
                                           : -1;
          set = n >= 0 ? (j < 14 && i >= 1 && i < 6 &&
                          (glyph[n][j / 2] & (1u << (5 - i))))
                       : (j == 0 || j == 15 || i == 0 || i == w - 1);
        }
        if (set)
          pixel(pixels, x + (int)used + (int)i, y + (int)line * 18 + (int)j,
                color);
      }
    used += w;
  }
  r.consumed = (unsigned)(s - start);
  r.lines = line + 1;
  if (r.truncated) {
    int end = x + (int)maxw - 12, yy = y + (int)(r.lines - 1) * 18 + 14;
    if (yy < 432)
      for (int i = 0; i < 3; i++)
        pixel(pixels, end + i * 4, yy, color);
  }
  return r;
}
