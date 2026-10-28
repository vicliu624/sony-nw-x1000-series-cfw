#include "../../native/ui_font.h"
#include "internal.h"
#include <limits.h>
uint16_t xw_rgb(unsigned r, unsigned g, unsigned b) {
  if (r > 255)
    r = 255;
  if (g > 255)
    g = 255;
  if (b > 255)
    b = 255;
  return (uint16_t)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
}
static xw_rect intersection(xw_rect a, xw_rect b) {
  long long x = a.x > b.x ? a.x : b.x, y = a.y > b.y ? a.y : b.y;
  long long right = (long long)a.x + a.width,
            bottom = (long long)a.y + a.height;
  if (right > (long long)b.x + b.width)
    right = (long long)b.x + b.width;
  if (bottom > (long long)b.y + b.height)
    bottom = (long long)b.y + b.height;
  if (a.width <= 0 || a.height <= 0 || b.width <= 0 || b.height <= 0 ||
      right <= x || bottom <= y)
    return (xw_rect){0, 0, 0, 0};
  return (xw_rect){(int)x, (int)y, (int)(right - x), (int)(bottom - y)};
}
void xw_clip(xw_app *a, xw_rect r) {
  if (a)
    a->clip = intersection(r, (xw_rect){0, 0, XW_WIDTH, XW_HEIGHT});
}
void xw_reset_clip(xw_app *a) {
  xw_clip(a, (xw_rect){0, 0, XW_WIDTH, XW_HEIGHT});
}
void xw_fill(xw_app *a, xw_rect r, uint16_t c) {
  if (!a)
    return;
  r = intersection(r, a->clip);
  for (int y = r.y; y < r.y + r.height; y++)
    for (int x = r.x; x < r.x + r.width; x++)
      a->pixels[y * XW_WIDTH + x] = c;
}
void xw_clear(xw_app *a, uint16_t c) {
  xw_fill(a, (xw_rect){0, 0, XW_WIDTH, XW_HEIGHT}, c);
}
static uint16_t blend(uint16_t bg, uint16_t fg, unsigned alpha) {
  unsigned r =
      (((bg >> 11) & 31) * (15 - alpha) + ((fg >> 11) & 31) * alpha + 7) / 15;
  unsigned g =
      (((bg >> 5) & 63) * (15 - alpha) + ((fg >> 5) & 63) * alpha + 7) / 15;
  unsigned b = ((bg & 31) * (15 - alpha) + (fg & 31) * alpha + 7) / 15;
  return (uint16_t)((r << 11) | (g << 5) | b);
}
int xw_text(xw_app *a, int x, int y, const char *s, unsigned scale,
            uint16_t color) {
  long long cursor = x;
  unsigned count = 0;
  if (!a || !s || scale < 1 || scale > 4)
    return -1;
  for (unsigned n = 0; s[n]; n++)
    if (n >= 4096 || (unsigned char)s[n] < 32 || (unsigned char)s[n] > 126)
      return -1;
  for (; *s; s++) {
    unsigned c = (unsigned char)*s - 32;
    count++;
    if (cursor > INT_MAX)
      return -1;
    for (unsigned row = 0; row < 16; row++)
      for (unsigned col = 0; col < hb_ui_advance[c] && col < 16; col++) {
        unsigned v = hb_ui_font[c][row][col / 2];
        v = (col & 1) ? (v & 15) : (v >> 4);
        /* The maintained font has up to sixteen raster columns. */
        for (unsigned sy = 0; v && sy < scale; sy++)
          for (unsigned sx = 0; sx < scale; sx++) {
            long long px = cursor + (long long)col * scale + sx,
                      py = (long long)y + row * scale + sy;
            if (px < a->clip.x || py < a->clip.y ||
                px >= (long long)a->clip.x + a->clip.width ||
                py >= (long long)a->clip.y + a->clip.height)
              continue;
            size_t pos = (size_t)py * XW_WIDTH + (size_t)px;
            a->pixels[pos] = blend(a->pixels[pos], color, v);
          }
      }
    cursor += hb_ui_advance[c] * scale;
  }
  return (int)count;
}
int xw_image(xw_app *a, int x, int y, unsigned w, unsigned h, const uint16_t *p,
             size_t n, int transparent, uint16_t key) {
  if (!a || !p || !w || !h || w > 4096 || h > 4096 || (size_t)w * h != n)
    return -1;
  xw_rect r = intersection((xw_rect){x, y, (int)w, (int)h}, a->clip);
  for (int j = r.y; j < r.y + r.height; j++)
    for (int i = r.x; i < r.x + r.width; i++) {
      uint16_t c =
          p[(size_t)((long long)j - y) * w + (size_t)((long long)i - x)];
      if (!transparent || c != key)
        a->pixels[j * XW_WIDTH + i] = c;
    }
  return 0;
}
void xw_button_draw(xw_app *a, xw_rect r, const char *label, int pressed) {
  xw_fill(a, r, pressed ? xw_rgb(43, 105, 92) : xw_rgb(54, 135, 119));
  xw_text(a, r.x + 10, r.y + (r.height - 16) / 2, label, 1,
          xw_rgb(255, 253, 245));
}
