#ifndef X1000_BITMAP_FONT_H
#define X1000_BITMAP_FONT_H
#include <stdint.h>

/* The legacy aggregate header may already have declared the same ABI type. */
#ifndef X1000_DICTIONARY_H
struct dx_font {
    unsigned char *data;
};
#endif

int dx_font_open(struct dx_font *, const char *);
void dx_font_close(struct dx_font *);
unsigned dx_utf8(const char **);
unsigned dx_width(const struct dx_font *, unsigned);
void dx_draw(const struct dx_font *, uint16_t *, int, int, const char *, uint16_t);
#endif
