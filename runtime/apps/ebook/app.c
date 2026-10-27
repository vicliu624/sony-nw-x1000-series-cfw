#include "../emulators/platform.h"
#include "../../native/frontend.h"
#include "ui.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#ifndef ER_APP_VERSION
#define ER_APP_VERSION "development"
#endif
static struct er_ui ui;
int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "--help")) {
    puts("X1000 EBook: local TXT/EPUB shelf, UTF-8/GB18030/UTF-16, touch page "
         "turns, 16/20/24px text, paper/warm/night themes and bounded "
         "progress. Books: /contents/HOMEBREW/data/ebook/books. Progress only on verified exposed "
         "storage; no firmware updates.");
    return 0;
  }
  if (argc == 2 && !strcmp(argv[1], "--version")) {
    puts(ER_APP_VERSION);
    return 0;
  }
  if (argc != 1)
    return 64;
  const char *font = "/contents/HOMEBREW/apps/ebook/assets/font.bin",
             *map = "/contents/HOMEBREW/apps/ebook/assets/gb18030.bin";
  char resolved[4096];
  if (!realpath(font, resolved) || strcmp(font, resolved) ||
      !realpath(map, resolved) || strcmp(map, resolved)) {
    memset(&ui, 0, sizeof ui);
    ui.mode = ER_ERROR;
    strcpy(ui.error, "EBOOK ASSETS NOT FOUND");
  } else if (er_ui_init(&ui, font, map))
    er_ui_shelf(&ui);
  er_ui_render(&ui);
  struct ep platform;
  if (ep_open(&platform)) {
    er_ui_close(&ui);
    return 2;
  }
  ep_present(&platform);
  int touching = 0, sx = 0, sy = 0, origin = -1, cancel = 0;
  uint32_t checkpoint = ep_now();
  while (!ep_stop && !ui.quit && !platform.display.failed) {
    int redraw = 0;
    if (platform.keys >= 0) {
      unsigned char events[128];
      ssize_t n = read(platform.keys, events, sizeof events);
      if (n > 0 && n % 16 == 0) {
        for (unsigned i = 0; i < (unsigned)n; i += 16)
          if (events[i + 8] == 1 && events[i + 9] == 0 && events[i + 11] == 0 &&
              events[i + 12] == 1) {
            unsigned code = events[i + 10];
            if (code == 18)
              ui.quit = 1;
            else if (code == 1 || code == 2) {
              er_ui_turn(&ui, code == 1);
              redraw = 1;
            }
          }
      } else if (!n || (n < 0 && errno != EAGAIN && errno != EINTR)) {
        close(platform.keys);
        platform.keys = -1;
      }
    }
    if (ui.quit)
      break;
    unsigned char raw[11];
    int got = hb_devices_next_touch(&platform.display, raw, 50);
    if (got < 0)
      break;
    if (got) {
      struct hb_touch t;
      hb_touch_decode(raw, &t);
      int x = (int)t.x, y = (int)t.y,
          hit = t.in_bounds ? er_ui_hit(ui.mode, x, y) : -1;
      if (t.down) {
        if (!touching) {
          sx = x;
          sy = y;
          origin = hit;
          cancel = 0;
        } else if (x - sx > 12 || sx - x > 12 || y - sy > 12 || sy - y > 12)
          cancel = 1;
        touching = 1;
        ui.pressed = cancel ? -1 : hit;
        if (ui.mode == ER_JUMP && hit == 40)
          er_ui_touch(&ui, x, y);
        redraw = 1;
      } else if (touching) {
        touching = 0;
        ui.pressed = -1;
        int dx = x - sx, dy = y - sy;
        if (ui.mode == ER_READING && t.in_bounds && sy >= 52 && sy < 384 &&
            y >= 52 && y < 384 && (dx > 40 || dx < -40) && dy < 60 &&
            dy > -60) {
          er_ui_turn(&ui, dx < 0);
        } else if (!cancel && hit == origin && dx <= 12 && dx >= -12 &&
                   dy <= 12 && dy >= -12)
          er_ui_touch(&ui, x, y);
        redraw = 1;
      }
    }
    uint32_t now = ep_now();
    if (!ep_stop && ui.book.file && ui.dirty &&
        (uint32_t)(now - checkpoint) >= 30000) {
      if (!er_ui_save(&ui)) {
        strcpy(ui.notice, "进度暂未保存，请检查存储");
        ui.discard = 0;
      }
      checkpoint = now;
      redraw = 1;
    }
    if (redraw && !ui.quit) {
      er_ui_render(&ui);
      ep_present(&platform);
    }
    hb_devices_flush(&platform.display);
  }
  if (!ep_stop)
    er_ui_save(&ui);
  er_ui_close(&ui);
  return ep_close(&platform) ? 2 : 0;
}
