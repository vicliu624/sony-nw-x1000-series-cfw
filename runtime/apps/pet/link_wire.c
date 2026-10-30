#include "link_wire.h"
#include <string.h>
static void put64(unsigned char *p, uint64_t v) {
  for (unsigned i = 0; i < 8; i++)
    p[7 - i] = (unsigned char)(v >> (i * 8));
}
static uint64_t get64(const unsigned char *p) {
  uint64_t n = 0;
  for (unsigned i = 0; i < 8; i++)
    n = (n << 8) | p[i];
  return n;
}
static int text_ok(const unsigned char *p, unsigned n) {
  for (unsigned i = 0; i < n;) {
    unsigned c = p[i], k, cp;
    if (c < 128) {
      if (c < 32 && c != '\n')
        return 0;
      i++;
      continue;
    }
    if (c >= 0xc2 && c <= 0xdf) {
      k = 2;
      cp = c & 31;
    } else if (c >= 0xe0 && c <= 0xef) {
      k = 3;
      cp = c & 15;
    } else if (c >= 0xf0 && c <= 0xf4) {
      k = 4;
      cp = c & 7;
    } else
      return 0;
    if (i + k > n)
      return 0;
    for (unsigned j = 1; j < k; j++) {
      if ((p[i + j] & 0xc0) != 0x80)
        return 0;
      cp = (cp << 6) | (p[i + j] & 63);
    }
    if ((k == 3 && cp < 0x800) || (k == 4 && cp < 0x10000) || cp > 0x10ffff ||
        (cp >= 0xd800 && cp <= 0xdfff))
      return 0;
    i += k;
  }
  return 1;
}
int pet_link_encode(const struct pet_link_snapshot *s, unsigned char *out,
                    size_t cap, size_t *used) {
  if (!s || !out || !used || s->state > PET_LINK_INTERRUPTED || cap < 36)
    return 0;
  const char *fields[] = {s->thread, s->turn, s->title, s->summary,
                          s->question};
  const unsigned limits[] = {128, 128, 96, 768, 768};
  unsigned sizes[5];
  size_t n = 36;
  for (unsigned i = 0; i < 5; i++) {
    unsigned j = 0;
    while (j <= limits[i] && fields[i][j])
      j++;
    if (j > limits[i] || !text_ok((const unsigned char *)fields[i], j))
      return 0;
    sizes[i] = j;
    n += j;
  }
  if (n > cap || n > PET_LINK_FRAME_MAX)
    return 0;
  memcpy(out, "PTSNAP01", 8);
  put64(out + 8, s->nonce);
  put64(out + 16, s->revision);
  out[24] = (unsigned char)s->state;
  out[25] = 0;
  size_t pos = 36;
  for (unsigned i = 0; i < 5; i++) {
    out[26 + i * 2] = (unsigned char)(sizes[i] >> 8);
    out[27 + i * 2] = (unsigned char)sizes[i];
    memcpy(out + pos, fields[i], sizes[i]);
    pos += sizes[i];
  }
  *used = n;
  return 1;
}
int pet_link_decode(struct pet_link_snapshot *s, const unsigned char *p,
                    size_t n, uint64_t nonce) {
  if (!s || !p || n < 36 || n > PET_LINK_FRAME_MAX ||
      memcmp(p, "PTSNAP01", 8) || get64(p + 8) != nonce ||
      p[24] > PET_LINK_INTERRUPTED || p[25])
    return 0;
  struct pet_link_snapshot value;
  memset(&value, 0, sizeof value);
  char *fields[] = {value.thread, value.turn, value.title, value.summary,
                    value.question};
  const unsigned limits[] = {128, 128, 96, 768, 768};
  size_t pos = 36;
  for (unsigned i = 0; i < 5; i++) {
    unsigned len = (unsigned)p[26 + i * 2] << 8 | p[27 + i * 2];
    if (len > limits[i] || len > n - pos || !text_ok(p + pos, len))
      return 0;
    memcpy(fields[i], p + pos, len);
    pos += len;
  }
  if (pos != n)
    return 0;
  value.nonce = nonce;
  value.revision = get64(p + 16);
  value.state = p[24];
  *s = value;
  return 1;
}
