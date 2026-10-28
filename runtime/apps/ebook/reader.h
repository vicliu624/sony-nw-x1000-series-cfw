#ifndef X1000_EBOOK_READER_H
#define X1000_EBOOK_READER_H
#include "../../../sdk/include/x1000/services/unicode_font.h"
#include <stdint.h>
#include <stdio.h>
enum { ER_AUTO, ER_UTF8, ER_GB18030, ER_UTF16LE, ER_UTF16BE };
struct er_maps {
  unsigned char *bytes;
  unsigned pairs, ranges;
};
struct ep_book;
struct er_book {
  FILE *file;
  struct ep_book *epub;
  uint32_t bytes, start, current, next, cache_base;
  unsigned cache_used;
  unsigned encoding, requested, size;
  volatile int *stop;
  struct dx_font *font;
  unsigned char cache[8192];
  unsigned char identity[32];
  struct er_maps *maps;
};
struct er_page {
  char lines[20][160];
  unsigned count;
  uint32_t next;
};
int er_maps_open(struct er_maps *, const char *);
void er_maps_close(struct er_maps *);
int er_open(struct er_book *, const char *, unsigned, struct er_maps *);
void er_close(struct er_book *);
int er_decode(struct er_book *, uint32_t, unsigned *, uint32_t *);
unsigned er_rows(unsigned);
int er_page_at(struct er_book *, uint32_t, struct er_page *);
int er_previous(struct er_book *, uint32_t, uint32_t *);
int er_align(struct er_book *, uint32_t, uint32_t *);
void er_text(const struct dx_font *, uint16_t *, int, int, const char *,
             unsigned, uint16_t, unsigned);
#endif
