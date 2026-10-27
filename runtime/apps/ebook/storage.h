#ifndef X1000_EBOOK_STORAGE_H
#define X1000_EBOOK_STORAGE_H
#include "reader.h"
#define ER_MAX_BOOKS 128
#define ER_STATE_BYTES 6208
struct er_item {
  char name[256];
  uint32_t bytes;
};
struct er_mark {
  unsigned char key[32];
  uint32_t bytes, offset;
  unsigned size, theme, encoding,format,chapter;
};
struct er_state {
  struct er_mark marks[128];
  uint32_t sequence, cursor;
};
struct er_storage {
  unsigned long long device;
  int ready, warning;
  struct er_state state;
};
int er_state_decode(struct er_state *, const unsigned char *, unsigned);
void er_state_encode(const struct er_state *, unsigned char[ER_STATE_BYTES]);
struct er_mark *er_state_find(struct er_state *, const unsigned char[32]);
void er_state_update(struct er_state *, const struct er_book *, unsigned);
int er_storage_open(struct er_storage *);
int er_storage_save(struct er_storage *);
int er_books_scan(struct er_item[ER_MAX_BOOKS]);
#endif
