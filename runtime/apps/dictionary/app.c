#include "../emulators/platform.h"
#include "../../../sdk/include/x1000/services/touch.h"
#include "ui.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static struct dx_ui ui;
static const char *base = "/contents/HOMEBREW/apps/dictionary/assets/";
int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "--help")) {
    puts("Offline English-Chinese dictionary. Nine-key multi-tap input, prefix "
         "results, definition pages, Chinese/IPA glyphs. Read-only assets, no "
         "network or storage writes.");
    return 0;
  }
  if (argc == 4 && !strcmp(argv[1], "--lookup")) {
    struct dx d;
    uint32_t index;
    char word[64], body[65536];
    if (!dx_open(&d, argv[2]))
      return 2;
    int ok = dx_lower(&d, argv[3], &index) && index < d.count &&
             dx_word(&d, index, word) && !strcasecmp(word, argv[3]) &&
             dx_text(&d, index, body, sizeof body);
    if (ok)
      puts(body);
    dx_close(&d);
    return ok ? 0 : 3;
  }
  if (argc != 1)
    return 64;
  char dict[256], font[256], resolved[4096];
  snprintf(dict, sizeof dict, "%slexicon.dic", base);
  snprintf(font, sizeof font, "%sfont.bin", base);
  if (!realpath(dict, resolved) || strcmp(dict, resolved) ||
      !realpath(font, resolved) || strcmp(font, resolved)) {
    memset(&ui, 0, sizeof ui);
    ui.mode = DX_ERROR;
    strcpy(ui.error, "DICTIONARY ASSETS NOT FOUND");
  } else
    dx_ui_open(&ui, dict, font);
  dx_ui_render(&ui);
  struct ep platform;
  if (ep_open(&platform)) {
    dx_ui_close(&ui);
    return 2;
  }
  ep_present(&platform);
  int touching = 0, origin = -1, sx = 0, sy = 0, cancel = 0;
  while (!ep_stop && !ui.quit && !platform.display.failed) {
    if (platform.keys >= 0) {
      unsigned char events[128];
      ssize_t n = read(platform.keys, events, sizeof events);
      if (n > 0 && n % 16 == 0) {
        for (unsigned i = 0; i < (unsigned)n; i += 16)
          if (events[i + 8] == 1 && events[i + 9] == 0 &&
              events[i + 10] == 18 && events[i + 11] == 0 &&
              events[i + 12] == 1)
            ui.quit = 1;
      } else if (n == 0 || (n < 0 && errno != EAGAIN && errno != EINTR)) {
        close(platform.keys);
        platform.keys = -1;
      }
    }
    if (ui.quit)
      break;
    int redraw = dx_ui_tick(&ui, ep_now());
    unsigned char raw[11];
    int got = hb_devices_next_touch(&platform.display, raw, 50);
    if (got < 0)
      break;
    if (got) {
      struct hb_touch t;
      hb_touch_decode(raw, &t);
      int hit = t.in_bounds ? dx_ui_hit(ui.mode, (int)t.x, (int)t.y) : -1;
      if (t.down) {
        if (!touching) {
          sx = (int)t.x;
          sy = (int)t.y;
          origin = hit;
          cancel = 0;
        } else if ((int)t.x - sx > 12 || sx - (int)t.x > 12 ||
                   (int)t.y - sy > 12 || sy - (int)t.y > 12)
          cancel = 1;
        touching = 1;
        ui.pressed = cancel ? -1 : hit;
        redraw = 1;
      } else if (touching) {
        touching = 0;
        ui.pressed = -1;
        if (!cancel && hit == origin && (int)t.x - sx <= 12 &&
            sx - (int)t.x <= 12 && (int)t.y - sy <= 12 && sy - (int)t.y <= 12)
          dx_ui_touch(&ui, (int)t.x, (int)t.y, ep_now());
        redraw = 1;
      }
    }
    if (redraw && !ui.quit) {
      dx_ui_render(&ui);
      ep_present(&platform);
    }
    hb_devices_flush(&platform.display);
  }
  dx_ui_close(&ui);
  return ep_close(&platform) ? 2 : 0;
}
