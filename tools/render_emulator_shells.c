/* PC-only visual fixture. Display regions are copied 1:1. */
#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
  for (int tama = 0; tama < 2; tama++)
    for (int pressed = 0; pressed < 2; pressed++) {
      ep_clear();
      ep_title(tama ? "TAMAGOTCHI ID" : "GAME BOY COLOR");
      ep_controls(tama, pressed ? EP_A : 0);
      unsigned w = tama ? 128 : 160, h = tama ? 128 : 144, x = tama ? 56 : 40,
               y = tama ? 86 : 48;
      for (unsigned j = 0; j < h; j++)
        for (unsigned i = 0; i < w;
             i++) { /* Deliberately synthetic pixels, no game ROM artwork. */
          unsigned r = (i * 31 / w), g = (j * 63 / h),
                   b = ((i / 8 + j / 8) % 2 ? 20 : 8);
          ep_canvas[(j + y) * 240 + x + i] = (r << 11) | (g << 5) | b;
        }
      char name[128];
      snprintf(name, sizeof name, "work/emulator-apps/%s%s.rgb565",
               tama ? "tama-shell" : "gbc-shell", pressed ? "-pressed" : "");
      FILE *f = fopen(name, "wb");
      assert(f);
      assert(fwrite(ep_canvas, 2, 240 * 432, f) == 240 * 432);
      assert(!fclose(f));
    }
  return 0;
}
