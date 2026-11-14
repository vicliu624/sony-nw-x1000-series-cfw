#include "bitmap_font.h"
#include "asset_io.h"
enum {
    FONT_GLYPHS = 65536,
    FONT_HEADER_BYTES = 16,
    FONT_HEIGHT = 16,
    FONT_NARROW = 8,
    FONT_WIDE = 16,
    FONT_GLYPH_BYTES = 32,
    FONT_FILE_BYTES = FONT_HEADER_BYTES + FONT_GLYPHS + FONT_GLYPHS * FONT_GLYPH_BYTES,
    SURFACE_WIDTH = 240,
    SURFACE_HEIGHT = 432,
    TEXT_RIGHT_EDGE = 236
};
int dx_font_open(struct dx_font *f, const char *path) {
    unsigned size;
    memset(f, 0, sizeof(*f));
    FILE *p = asset_open_readonly(path, FONT_FILE_BYTES, &size);
    if (!p)
        return 0;
    if (size != FONT_FILE_BYTES) {
        fclose(p);
        return 0;
    }
    f->data = malloc(size);
    int ok = f->data && fread(f->data, 1, size, p) == size && !memcmp(f->data, "XFONT1\0\0", 8) &&
             asset_le32(f->data + 8) == FONT_GLYPHS && asset_le32(f->data + 12) == FONT_HEIGHT;
    fclose(p);
    if (!ok) {
        dx_font_close(f);
        return 0;
    }
    for (unsigned i = 0; i < FONT_GLYPHS; i++)
        if (f->data[FONT_HEADER_BYTES + i] != 0 && f->data[FONT_HEADER_BYTES + i] != FONT_NARROW &&
            f->data[FONT_HEADER_BYTES + i] != FONT_WIDE) {
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
    if (cp >= FONT_GLYPHS)
        cp = 0xfffd;
    return f->data && f->data[FONT_HEADER_BYTES + cp] ? f->data[FONT_HEADER_BYTES + cp]
           : cp < 128                                 ? FONT_NARROW
                                                      : FONT_WIDE;
}
void dx_draw(const struct dx_font *f, uint16_t *pixels, int x, int y, const char *s,
             uint16_t color) {
    while (*s) {
        unsigned cp = dx_utf8(&s);
        if (cp >= FONT_GLYPHS)
            cp = 0xfffd;
        unsigned w = dx_width(f, cp);
        if (x + (int)w > TEXT_RIGHT_EDGE)
            break;
        const unsigned char *b =
            f->data && f->data[FONT_HEADER_BYTES + cp]
                ? f->data + FONT_HEADER_BYTES + FONT_GLYPHS + cp * FONT_GLYPH_BYTES
                : 0;
        for (int j = 0; j < FONT_HEIGHT; j++)
            for (unsigned i = 0; i < w; i++) {
                int set = b ? !!((b[j * 2] << 8 | b[j * 2 + 1]) & (0x8000u >> i))
                            : (j == 0 || j == FONT_HEIGHT - 1 || i == 0 || i == w - 1);
                if (set && x + (int)i >= 0 && x + (int)i < SURFACE_WIDTH && y + j >= 0 &&
                    y + j < SURFACE_HEIGHT)
                    pixels[(y + j) * SURFACE_WIDTH + x + i] = color;
            }
        x += (int)w;
    }
}
