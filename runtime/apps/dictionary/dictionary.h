#ifndef X1000_DICTIONARY_H
#define X1000_DICTIONARY_H
#include <stdint.h>
#include <stdio.h>
struct dx {
  FILE *file;
  uint32_t count, payload, bytes;
};
struct dx_font {
  unsigned char *data;
};
int dx_open(struct dx *, const char *);
void dx_close(struct dx *);
int dx_word(struct dx *, uint32_t, char out[64]);
int dx_lower(struct dx *, const char *, uint32_t *);
int dx_text(struct dx *, uint32_t, char *, unsigned);
int dx_font_open(struct dx_font *, const char *);
void dx_font_close(struct dx_font *);
unsigned dx_utf8(const char **);
unsigned dx_width(const struct dx_font *, unsigned);
void dx_draw(const struct dx_font *, uint16_t *, int, int, const char *,
             uint16_t);
struct dx_input {
  char query[64];
  int pending;
  unsigned cycle;
  uint32_t stamp;
};
void dx_input_init(struct dx_input *);
int dx_input_key(struct dx_input *, unsigned, uint32_t);
void dx_input_commit(struct dx_input *);
void dx_input_delete(struct dx_input *);
int dx_input_space(struct dx_input *);
#endif
