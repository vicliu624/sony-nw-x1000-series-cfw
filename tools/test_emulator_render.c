/* Verify the actual application renderer copies every guest pixel exactly once.
 */
#define main unused_emulator_entry
#include "../runtime/apps/emulators/app.c"
#undef main
#include <assert.h>
static uint16_t guest[160 * 144];
const uint16_t *gb_pixels(void) { return guest; }
const uint16_t *color_pixels(void) { return guest; }
int color_visible(void) { return 1; }
int main(void) {
#ifdef HB_TAMA_ID
  unsigned w = 128, h = 128, x = 56, y = 86;
#else
  unsigned w = 160, h = 144, x = 40, y = 48;
#endif
  for (unsigned j = 0; j < h; j++)
    for (unsigned i = 0; i < w; i++)
      guest[j * w + i] = (uint16_t)((i * 31 / w) << 11 | (j * 63 / h) << 5 |
                                    ((i / 8 + j / 8) % 2 ? 20 : 8));
  mode = GAME;
#ifndef HB_TAMA_ID
  audio.enabled=1;
#endif
  displayed_keys = 0;
  render();
  for (unsigned j = 0; j < h; j++)
    for (unsigned i = 0; i < w; i++)
      assert(ep_canvas[(j + y) * 240 + x + i] == guest[j * w + i]);
#ifndef HB_TAMA_ID
  /* Unchanged shell must not be repainted, but every guest pixel is refreshed. */
  ep_canvas[40 * 240 + 10] = 0x1234;
  guest[0] ^= 0xffff;
  render();
  assert(ep_canvas[40 * 240 + 10] == 0x1234);
  assert(ep_canvas[y * 240 + x] == guest[0]);
#endif
  #ifdef HB_TAMA_ID
  uint16_t old = ep_canvas[274 * 240 + 108];
#else
  uint16_t old = ep_canvas[232 * 240 + 200];
#endif
  displayed_keys = EP_A;
  render();
  for (unsigned j = 0; j < h; j++)
    for (unsigned i = 0; i < w; i++)
      assert(ep_canvas[(j + y) * 240 + x + i] == guest[j * w + i]);
  #ifdef HB_TAMA_ID
  assert(old != ep_canvas[274 * 240 + 108]);
#else
  assert(old != ep_canvas[232 * 240 + 200]);
#endif
  assert(ep_canvas[388 * 240] == 0x1a4b);
  printf("Actual app render: %u x %u one-to-one guest pixels, virtual shell "
         "and pressed-state render passed\n",
         w, h);
  char name[100];
  snprintf(name, sizeof name, "work/emulator-app-tests/render-%u.rgb565", w);
  FILE *f = fopen(name, "wb");
  assert(f);
  assert(fwrite(ep_canvas, 2, 240 * 432, f) == 240 * 432);
  assert(!fclose(f));
  return 0;
}
