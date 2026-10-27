#include "reader.h"
#include "epub/epub.h"
#include "../../native/sha256.h"
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
int er_maps_open(struct er_maps *m, const char *path) {
  memset(m, 0, sizeof(*m));
  FILE *f = fopen(path, "rb");
  if (!f)
    return 0;
  unsigned char head[16];
  int ok = fread(head, 1, 16, f) == 16 && !memcmp(head, "XGB1803\0", 8);
  if (!ok) {
    fclose(f);
    return 0;
  }
  m->pairs = le32(head + 8);
  m->ranges = le32(head + 12);
  if (m->pairs != 23940 || m->ranges > 512) {
    fclose(f);
    return 0;
  }
  unsigned n = m->pairs * 4 + m->ranges * 12;
  m->bytes = malloc(n);
  ok = m->bytes && fread(m->bytes, 1, n, f) == n && fgetc(f) == EOF;
  fclose(f);
  if (!ok) {
    er_maps_close(m);
    return 0;
  }
  unsigned end = 0;
  for (unsigned i = 0; i < m->ranges; i++) {
    unsigned char *p = m->bytes + m->pairs * 4 + i * 12;
    unsigned lo = le32(p), hi = le32(p + 4), cp = le32(p + 8);
    if (lo > hi || (i && lo <= end) || hi >= 1587600 || cp > 0x10ffff ||
        hi - lo > 0x10ffff - cp) {
      er_maps_close(m);
      return 0;
    }
    end = hi;
  }
  return 1;
}
void er_maps_close(struct er_maps *m) {
  free(m->bytes);
  memset(m, 0, sizeof(*m));
}
static int byte_at(struct er_book *b, uint32_t off) {
  if (off >= b->bytes || (b->stop && *b->stop))
    return -1;
  if (off < b->cache_base || off - b->cache_base >= b->cache_used) {
    uint32_t start = off & ~8191u;
    if (fseek(b->file, (long)start, SEEK_SET))
      return -1;
    b->cache_base = start;
    b->cache_used = (unsigned)fread(b->cache, 1, sizeof b->cache, b->file);
    if (off - start >= b->cache_used)
      return -1;
  }
  return b->cache[off - b->cache_base];
}
static unsigned map4(struct er_maps *m, unsigned n) {
  if (!m || !m->bytes)
    return 0xfffd;
  unsigned lo = 0, hi = m->ranges;
  while (lo < hi) {
    unsigned mid = lo + (hi - lo) / 2;
    unsigned char *p = m->bytes + m->pairs * 4 + mid * 12;
    if (le32(p) <= n)
      lo = mid + 1;
    else
      hi = mid;
  }
  if (!lo)
    return 0xfffd;
  unsigned char *p = m->bytes + m->pairs * 4 + (lo - 1) * 12;
  return n <= le32(p + 4) ? le32(p + 8) + n - le32(p) : 0xfffd;
}
int er_decode(struct er_book *b, uint32_t off, unsigned *out, uint32_t *next) {
  int a = byte_at(b, off);
  if (a < 0)
    return 0;
  *next = off + 1;
  *out = 0xfffd;
  if (b->encoding == ER_UTF16LE || b->encoding == ER_UTF16BE) {
    int z = byte_at(b, off + 1);
    if (z < 0)
      return 1;
    unsigned n = b->encoding == ER_UTF16LE ? (unsigned)a | ((unsigned)z << 8)
                                           : ((unsigned)a << 8) | (unsigned)z;
    *next = off + 2;
    if (n >= 0xd800 && n <= 0xdbff) {
      int c = byte_at(b, off + 2), d = byte_at(b, off + 3);
      if (c < 0 || d < 0)
        return 1;
      unsigned v = b->encoding == ER_UTF16LE ? (unsigned)c | ((unsigned)d << 8)
                                             : ((unsigned)c << 8) | (unsigned)d;
      if (v < 0xdc00 || v > 0xdfff)
        return 1;
      *next = off + 4;
      *out = 0x10000 + ((n - 0xd800) << 10) + v - 0xdc00;
      return 1;
    }
    if (n >= 0xdc00 && n <= 0xdfff)
      return 1;
    *out = n;
    return 1;
  }
  if (a < 128) {
    *out = (unsigned)a;
    return 1;
  }
  if (b->encoding == ER_GB18030) {
    int z = byte_at(b, off + 1);
    if (a < 0x81 || a > 0xfe || z < 0)
      return 1;
    if (z >= 0x30 && z <= 0x39) {
      int c = byte_at(b, off + 2), d = byte_at(b, off + 3);
      if (c < 0x81 || c > 0xfe || d < 0x30 || d > 0x39)
        return 1;
      *next = off + 4;
      *out = map4(b->maps,
                  (((unsigned)a - 0x81) * 10 + (unsigned)z - 0x30) * 1260 +
                      ((unsigned)c - 0x81) * 10 + (unsigned)d - 0x30);
      return 1;
    }
    if (z >= 0x40 && z <= 0xfe && z != 0x7f && b->maps && b->maps->bytes) {
      unsigned idx =
          ((unsigned)a - 0x81) * 190 + (unsigned)z - 0x40 - (z > 0x7f);
      *out = le32(b->maps->bytes + idx * 4);
      *next = off + 2;
    }
    return 1;
  }
  unsigned cp = (unsigned)a, n;
  if (a >= 0xc2 && a <= 0xdf) {
    cp &= 31;
    n = 2;
  } else if (a >= 0xe0 && a <= 0xef) {
    cp &= 15;
    n = 3;
  } else if (a >= 0xf0 && a <= 0xf4) {
    cp &= 7;
    n = 4;
  } else
    return 1;
  for (unsigned i = 1; i < n; i++) {
    int c = byte_at(b, off + i);
    if (c < 0 || (c & 0xc0) != 0x80)
      return 1;
    cp = (cp << 6) | ((unsigned)c & 63);
  }
  if ((n == 3 && cp < 0x800) || (n == 4 && cp < 0x10000) || cp > 0x10ffff ||
      (cp >= 0xd800 && cp <= 0xdfff))
    return 1;
  *out = cp;
  *next = off + n;
  return 1;
}
static int utf8_sample(struct er_book *b) {
  unsigned limit = b->bytes < 65536 ? b->bytes : 65536;
  unsigned original = b->encoding;
  b->encoding = ER_UTF8;
  uint32_t p = 0, next;
  unsigned cp;
  while (p < limit) {
    if (!er_decode(b, p, &cp, &next)) {
      b->encoding = original;
      return 0;
    }
    if ((cp == 0xfffd && next == p + 1) || cp == 0) {
      if (p + 4 >= limit && limit < b->bytes)
        break;
      b->encoding = original;
      return 0;
    }
    p = next;
  }
  b->encoding = original;
  return 1;
}
int er_open(struct er_book *b, const char *path, unsigned encoding,
            struct er_maps *m) {
  memset(b, 0, sizeof(*b));
  if (encoding > ER_UTF16BE)
    return 0;
  int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
  if (fd < 0)
    return 0;
  struct hb_target_stat st;
  if (hb_target_fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 ||
      st.st_size > 64 * 1024 * 1024) {
    close(fd);
    return 0;
  }
  b->file = fdopen(fd, "rb");
  if (!b->file) {
    close(fd);
    return 0;
  }
  b->bytes = (uint32_t)st.st_size;
  b->cache_base = 0xffffffffu;
  b->maps = m;
  b->size = 20;
  b->requested = encoding;
  b->encoding = encoding;
  int a = byte_at(b, 0), z = byte_at(b, 1), c = byte_at(b, 2);
  unsigned bom = a == 0xef && z == 0xbb && c == 0xbf ? ER_UTF8
                 : a == 0xff && z == 0xfe            ? ER_UTF16LE
                 : a == 0xfe && z == 0xff            ? ER_UTF16BE
                                                     : ER_AUTO;
  if (!encoding)
    b->encoding = bom ? bom : utf8_sample(b) ? ER_UTF8 : ER_GB18030;
  if (b->encoding == ER_GB18030 && (!m || !m->bytes)) {
    er_close(b);
    return 0;
  }
  b->start = bom == b->encoding ? (bom == ER_UTF8 ? 3 : 2) : 0;
  b->current = b->start;
  struct hb_sha256 h;
  hb_sha256_init(&h);
  hb_sha256_update(&h, (const unsigned char *)path, (unsigned)strlen(path));
  hb_sha256_update(&h, (const unsigned char *)&b->bytes, 4);
  unsigned char block[4096];
  unsigned n = b->bytes < sizeof block ? b->bytes : sizeof block;
  if (fseek(b->file, 0, SEEK_SET) || fread(block, 1, n, b->file) != n) {
    er_close(b);
    return 0;
  }
  hb_sha256_update(&h, block, n);
  if (b->bytes > sizeof block) {
    if (fseek(b->file, (long)(b->bytes - sizeof block), SEEK_SET) ||
        fread(block, 1, sizeof block, b->file) != sizeof block) {
      er_close(b);
      return 0;
    }
    hb_sha256_update(&h, block, sizeof block);
  }
  hb_sha256_final(&h, b->identity);
  size_t pathlen=strlen(path);
  if(pathlen>=5&&!strcasecmp(path+pathlen-5,".epub")){
    b->epub=epub_open(b->file,b->bytes);
    if(!b->epub){er_close(b);return 0;}
    b->current=b->start=0;b->encoding=ER_UTF8;
  }
  return 1;
}
void er_close(struct er_book *b) {
  if(b->epub)epub_close(b->epub);
  if (b->file)
    fclose(b->file);
  memset(b, 0, sizeof(*b));
}
unsigned er_rows(unsigned size) { return 326 / (size + 6); }
static unsigned encode(char *p, unsigned cp) {
  if (cp < 128) {
    p[0] = (char)cp;
    return 1;
  }
  if (cp < 0x800) {
    p[0] = 0xc0 | (cp >> 6);
    p[1] = 0x80 | (cp & 63);
    return 2;
  }
  if (cp < 0x10000) {
    p[0] = 0xe0 | (cp >> 12);
    p[1] = 0x80 | ((cp >> 6) & 63);
    p[2] = 0x80 | (cp & 63);
    return 3;
  }
  p[0] = 0xf0 | (cp >> 18);
  p[1] = 0x80 | ((cp >> 12) & 63);
  p[2] = 0x80 | ((cp >> 6) & 63);
  p[3] = 0x80 | (cp & 63);
  return 4;
}
static unsigned width(unsigned cp, unsigned size) {
  return (cp < 128 ? 8u : 16u) * size / 16;
}
static int closing(unsigned cp) {
  return cp == ',' || cp == '.' || cp == '!' || cp == '?' || cp == ':' ||
         cp == ';' || cp == 0x3001 || cp == 0x3002 || cp == 0xff0c ||
         cp == 0xff01 || cp == 0xff1f || cp == 0xff1b || cp == 0xff1a ||
         cp == 0xff09 || cp == 0x300b || cp == 0x3011 || cp == 0x3009 ||
         cp == 0x201d || cp == 0x2019 || cp == 0x300d || cp == 0x300f ||
         cp == 0x2026 || cp == 0x2014;
}
static int opening(unsigned cp) {
  return cp == 0xff08 || cp == 0x300a || cp == 0x3010 || cp == 0x3008 ||
         cp == 0x201c || cp == 0x2018 || cp == 0x300c || cp == 0x300e;
}
static int line(struct er_book *b, uint32_t at, char *out, uint32_t *next) {
  unsigned x = 0, n = 0, space_n = 0, last_n = 0, last_cp = 0;
  uint32_t p = at, space_next = at, last_source = at;
  *next = at;
  out[0] = 0;
  while (p < b->bytes) {
    unsigned cp;
    uint32_t after;
    if (!er_decode(b, p, &cp, &after))
      return -1;
    if (cp == '\r' || cp == '\n') {
      if (cp == '\r') {
        unsigned c;
        uint32_t z;
        if (er_decode(b, after, &c, &z) && c == '\n')
          after = z;
      }
      p = after;
      break;
    }
    if (cp == 0xfeff) {
      p = after;
      continue;
    }
    if (cp == '\t')
      cp = ' ';
    if (cp == 0)
      cp = 0xfffd;
    unsigned w =
        b->font ? dx_width(b->font, cp) * b->size / 16 : width(cp, b->size);
    if (x + w > 224) {
      if (space_n) {
        n = space_n;
        p = space_next;
      } else if (last_n && (closing(cp) || opening(last_cp))) {
        n = last_n;
        p = last_source;
      }
      break;
    }
    if (cp == ' ' && n) {
      space_n = n;
      space_next = after;
    }
    if (n + 4 >= 160)
      return -1;
    last_n = n;
    last_source = p;
    last_cp = cp;
    n += encode(out + n, cp);
    x += w;
    p = after;
  }
  out[n] = 0;
  *next = p;
  return p > at ? 1 : 0;
}
int er_page_at(struct er_book *b, uint32_t at, struct er_page *out) {
  memset(out, 0, sizeof(*out));
  if(b->epub){b->epub->stop=b->stop;if(!ep_layout(b->epub,at,b->size,b->font,0))return 0;out->count=b->epub->page.count;out->next=b->epub->page.next;b->next=out->next;return 1;}
  if (at < b->start || at > b->bytes)
    return 0;
  uint32_t p = at;
  for (unsigned i = 0; i < er_rows(b->size) && p < b->bytes; i++) {
    uint32_t next;
    int r = line(b, p, out->lines[i], &next);
    if (r < 0 || !r || next <= p)
      return 0;
    out->count++;
    p = next;
  }
  out->next = p;
  b->next = p;
  return 1;
}
static uint32_t paragraph(struct er_book *b, uint32_t before) {
  if (before <= b->start)
    return b->start;
  unsigned step =
      b->encoding == ER_UTF16LE || b->encoding == ER_UTF16BE ? 2 : 1;
  if (step == 2)
    before = b->start + ((before - b->start) / 2) * 2;
  uint32_t p = before;
  while (p > b->start) {
    p -= step;
    int a = byte_at(b, p), z = step == 2 ? byte_at(b, p + 1) : 0;
    if (a < 0)
      return b->start;
    if ((step == 1 && a == 10) ||
        (step == 2 && (b->encoding == ER_UTF16LE ? (a == 10 && z == 0)
                                                 : (a == 0 && z == 10))))
      return p + step;
  }
  return b->start;
}
int er_align(struct er_book *b, uint32_t target, uint32_t *out) {
  if(b->epub){*out=target>b->epub->doc->count?0:target;return 1;}
  if (target >= b->bytes)
    target = b->bytes ? b->bytes - 1 : b->start;
  uint32_t p = paragraph(b, target);
  char text[160];
  while (p < target) {
    uint32_t next;
    int r = line(b, p, text, &next);
    if (r < 0)
      return 0;
    if (!r || next > target)
      break;
    p = next;
  }
  *out = p;
  return 1;
}
int er_previous(struct er_book *b, uint32_t current, uint32_t *out) {
  if(b->epub)return ep_previous(b->epub,current,b->size,b->font,out);
  if (current <= b->start) {
    *out = b->start;
    return 1;
  }
  uint32_t anchor = current - b->start > 4096 ? paragraph(b, current - 4096)
                                              : b->start,
           p = anchor, ring[20] = {0};
  unsigned count = 0, rows = er_rows(b->size);
  char text[160];
  while (p < current) {
    ring[count % rows] = p;
    count++;
    uint32_t next;
    int r = line(b, p, text, &next);
    if (r <= 0)
      return 0;
    if (next >= current)
      break;
    p = next;
  }
  *out = count >= rows ? ring[(count - rows) % rows] : anchor;
  return 1;
}
static uint16_t blend(uint16_t bg, uint16_t fg, unsigned alpha) {
  unsigned r =
      (((bg >> 11) & 31) * (256 - alpha) + ((fg >> 11) & 31) * alpha + 128) >>
      8;
  unsigned g =
      (((bg >> 5) & 63) * (256 - alpha) + ((fg >> 5) & 63) * alpha + 128) >> 8;
  unsigned b = ((bg & 31) * (256 - alpha) + (fg & 31) * alpha + 128) >> 8;
  return (uint16_t)((r << 11) | (g << 5) | b);
}
void er_text(const struct dx_font *f, uint16_t *surface, int x, int y,
             const char *s, unsigned size, uint16_t color, unsigned limit) {
  if (!size || size > 64)
    return;
  unsigned first[64], last[64], weight[64];
  for (unsigned k = 0; k < size; k++) {
    unsigned a = k * 16, z = a + 16;
    first[k] = a / size;
    last[k] = (z - 1) / size;
    unsigned end = (first[k] + 1) * size;
    weight[k] = (end < z ? end : z) - a;
  }
  unsigned used = 0;
  while (*s) {
    unsigned cp = dx_utf8(&s);
    if (cp > 65535)
      cp = 0xfffd;
    unsigned base = dx_width(f, cp), w = base * size / 16;
    if (used + w > limit)
      break;
    const unsigned char *b =
        f->data && f->data[16 + cp] ? f->data + 16 + 65536 + cp * 32 : 0;
    for (unsigned j = 0; j < size; j++)
      for (unsigned i = 0; i < w; i++) {
        if (x + (int)used + (int)i < 0 || x + (int)used + (int)i >= 240 ||
            y + (int)j < 0 || y + (int)j >= 432)
          continue;
        unsigned alpha = 0;
        if (!b) {
          if (j == 0 || j == size - 1 || i == 0 || i == w - 1)
            alpha = 256;
        } else {
          unsigned rows[2] = {first[j], last[j]}, cols[2] = {first[i], last[i]},
                   wy[2] = {weight[j], 16 - weight[j]},
                   wx[2] = {weight[i], 16 - weight[i]};
          for (unsigned yy = 0; yy < 2; yy++)
            for (unsigned xx = 0; xx < 2; xx++)
              if (cols[xx] < base &&
                  ((b[rows[yy] * 2] << 8 | b[rows[yy] * 2 + 1]) &
                   (0x8000u >> cols[xx])))
                alpha += wy[yy] * wx[xx];
        }
        if (alpha) {
          unsigned p = (y + j) * 240 + x + used + i;
          surface[p] = alpha == 256 ? color : blend(surface[p], color, alpha);
        }
      }
    used += w;
  }
}
