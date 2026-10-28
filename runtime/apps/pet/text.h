#ifndef HB_PET_TEXT_H
#define HB_PET_TEXT_H
#include <stdio.h>
struct pet_glyph {
  unsigned cp, width, valid;
  unsigned char bits[32];
};
struct pet_font {
  FILE *file;
  unsigned next;
  struct pet_glyph cache[64];
};
struct pet_text_result {
  unsigned consumed, lines, truncated, missing;
};
int pet_font_open(struct pet_font *, const char *);
void pet_font_close(struct pet_font *);
unsigned pet_utf8(const char **);
unsigned pet_text_width(struct pet_font *, const char *);
struct pet_text_result pet_text(struct pet_font *, unsigned short *, int, int,
                                unsigned, unsigned, const char *,
                                unsigned short);
void pet_ui_font(struct pet_font *);
#endif
