#include "../../../sdk/include/x1000/services/display.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include "../../../sdk/include/x1000/services/touch.h"
#include "link_pair.h"
#include "link_ui.h"
#include "storage.h"
#include "text.h"
#include "ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#ifndef HB_PET_VERSION
#error Build with the application VERSION
#endif
static unsigned short canvas[HB_DISPLAY_PIXELS];
static volatile int stop;
static int load_pair(struct pet_storage *storage, struct pet_pair *pair) {
  unsigned char bytes[PET_PAIR_MAX];
  int size = pet_storage_read_pair(storage, bytes, sizeof bytes);
  int ok = size > 0 && pet_pair_decode(pair, bytes, (unsigned)size);
  volatile unsigned char *p = bytes;
  for (unsigned i = 0; i < sizeof bytes; i++)
    p[i] = 0;
  return ok;
}
/* libc times uses four stock 32-bit longs and elapsed kernel ticks. */
extern long pet_times(void *) __asm__("times");
static unsigned long long milliseconds(void) {
  long values[4];
  long rate = sysconf(_SC_CLK_TCK);
  unsigned long ticks = (unsigned long)pet_times(values);
  return rate > 0 ? (unsigned long long)ticks * 1000 / (unsigned long)rate : 0;
}
static unsigned char *assets(const char *executable) {
  char path[4096];
  const char *slash = strrchr(executable, '/');
  if (!slash || slash - executable > 4000)
    return 0;
  snprintf(path, sizeof path, "%.*s/sprites.bin", (int)(slash - executable),
           executable);
  FILE *f = fopen(path, "rb");
  if (!f)
    return 0;
  unsigned n = 9 * 8 * 96 * 104 * 3;
  unsigned char *p = malloc(n);
  if (!p) {
    fclose(f);
    return 0;
  }
  int ok = fread(p, 1, n, f) == n && fgetc(f) == EOF && !ferror(f);
  if (fclose(f))
    ok = 0;
  if (!ok) {
    free(p);
    return 0;
  }
  return p;
}
int pet_run(const char *executable) {
  stop = 0;
  if (hb_stop_signals_install(&stop))
    return 2;
  unsigned char *sprites = assets(executable);
  if (!sprites) {
    fputs("Pet: missing or invalid sprites.bin\n", stderr);
    return 2;
  }
  struct pet_font font;
  char font_path[4096];
  const char *slash = strrchr(executable, '/');
  snprintf(font_path, sizeof font_path, "%.*s/font.bin",
           (int)(slash - executable), executable);
  if (!pet_font_open(&font, font_path)) {
    free(sprites);
    fputs("Pet: missing or invalid font.bin\n", stderr);
    return 2;
  }
  pet_ui_font(&font);
  struct pet_ui ui;
  pet_ui_init(&ui);
  struct pet_storage storage;
  int loaded = pet_storage_open(&storage, &ui.pet.state);
  ui.save_warning = loaded < 0;
  if (loaded < 0)
    ui.pet.message = loaded == -2 ? "SAVE DAMAGED  RESET" : "SAVE UNAVAILABLE";
  if (ui.pet.state.sleeping) {
    ui.pet.pose = PET_ASLEEP;
    if (loaded >= 0)
      ui.pet.message = "RESTING  TAP TO WAKE";
  }
  struct pet_pair pair;
  memset(&pair, 0, sizeof pair);
  struct pet_net *net = 0;
  if (load_pair(&storage, &pair)) {
    net = pet_net_create(&pair.net, &stop);
    ui.paired = net != 0;
    ui.link_enabled = net != 0;
    memcpy(ui.computer, pair.computer, sizeof ui.computer);
  }
  ui.net_state = net ? PET_NET_CONNECTING : PET_NET_STOPPED;
  struct hb_devices devices;
  pet_ui_draw(&ui, canvas, sprites);
  if (hb_devices_open(&devices, canvas, HB_DISPLAY_PIXELS, &stop)) {
    pet_net_destroy(net);
    pet_storage_close(&storage);
    pet_ui_font(0);
    pet_font_close(&font);
    free(sprites);
    return stop ? 0 : 2;
  }
  hb_devices_present(&devices);
  unsigned long long last = milliseconds();
  int pressed = 0, cancel = 0, x = 0, y = 0, failed = 0;
  unsigned checkpoint_ms = 0;
  unsigned redraw_ms = 0;
  while (!stop && !ui.exit_requested && !devices.failed) {
    unsigned char packet[11];
    int got = hb_devices_next_touch(&devices, packet, 50);
    if (got < 0) {
      if (got == -2)
        failed = 1;
      break;
    }
    unsigned long long now = milliseconds();
    unsigned elapsed =
        now >= last && now - last <= 1000 ? (unsigned)(now - last) : 0;
    last = now;
    int fresh = pet_net_tick(net, now);
    int link_update = 0;
    enum pet_net_state previous = ui.net_state;
    ui.net_state = pet_net_status(net, now);
    ui.discovered = pet_net_endpoint(net, ui.peer);
    if (fresh) {
      const struct pet_link_snapshot *s = pet_net_snapshot(net);
      int first = !ui.link.thread[0];
      int changed = strcmp(ui.link.thread, s->thread) ||
                    strcmp(ui.link.turn, s->turn) ||
                    ui.link.revision != s->revision;
      link_update = changed || ui.link.state != s->state;
      if (strcmp(ui.link.thread, s->thread) || strcmp(ui.link.turn, s->turn))
        ui.acknowledged = 0;
      if (first && s->state == PET_LINK_COMPLETED)
        ui.acknowledged = s->revision;
      ui.link = *s;
      if (changed)
        ui.detail_page = 0;
    }
    pet_tick(&ui.pet, elapsed);
    ui.animation_ms = (ui.animation_ms + elapsed) % 60000;
    checkpoint_ms += elapsed;
    redraw_ms += elapsed;
    if (checkpoint_ms >= 60000 && !stop) {
      checkpoint_ms = 0;
      ui.save_warning = !pet_storage_save(&storage, &ui.pet.state, &stop);
    }
    if (got) {
      struct hb_touch touch;
      hb_touch_decode(packet, &touch);
      if (touch.down) {
        if (!pressed) {
          x = touch.x;
          y = touch.y;
          cancel = 0;
        }
        pressed = 1;
        if (!touch.in_bounds || abs((int)touch.x - x) > 16 ||
            abs((int)touch.y - y) > 16)
          cancel = 1;
      } else if (pressed) {
        pressed = 0;
        if (!cancel && touch.in_bounds) {
          struct pet_state before = ui.pet.state;
          pet_ui_tap(&ui, x, y);
          if (memcmp(&before, &ui.pet.state, sizeof before) && !stop)
            ui.save_warning = !pet_storage_save(&storage, &ui.pet.state, &stop);
        }
      }
    }
    if (ui.exit_requested && !ui.discard && !stop) {
      if (!pet_storage_save(&storage, &ui.pet.state, &stop)) {
        ui.exit_requested = 0;
        ui.page = PET_SAVE_ERROR;
      }
    }
    if (ui.link_command && !stop) {
      int command = ui.link_command;
      ui.link_command = PET_LINK_CMD_NONE;
      ui.link_error = 0;
      pet_net_destroy(net);
      net = 0;
      ui.link_enabled = 0;
      if (command == PET_LINK_CMD_CONNECT) {
        if (!load_pair(&storage, &pair)) {
          ui.paired = 0;
          ui.link_error = 1;
        } else {
          net = pet_net_create(&pair.net, &stop);
          ui.link_enabled = net != 0;
          ui.paired = net != 0;
          if (!net)
            ui.link_error = 1;
        }
      }
      if (command == PET_LINK_CMD_FORGET) {
        if (!pet_storage_forget_pair(&storage, &stop))
          ui.link_error = 1;
        else {
          ui.paired = 0;
          memset(&ui.link, 0, sizeof ui.link);
          memset(&pair, 0, sizeof pair);
          ui.computer[0] = 0;
        }
      }
      ui.net_state = net ? PET_NET_CONNECTING : PET_NET_STOPPED;
    }
    if (got || link_update || previous != ui.net_state ||
        (ui.page == PET_ROOM && redraw_ms >= 100)) {
      pet_ui_draw(&ui, canvas, sprites);
      hb_devices_present(&devices);
      redraw_ms = 0;
    }
    hb_devices_flush(&devices);
  }
  /* Manager stop (including HOME/USB handoff) never starts storage writes. */
  pet_net_destroy(net);
  memset(&pair, 0, sizeof pair);
  pet_storage_close(&storage);
  pet_ui_font(0);
  pet_font_close(&font);
  free(sprites);
  if (hb_devices_close(&devices))
    failed = 1;
  return failed || devices.failed ? 2 : 0;
}
#ifndef PET_APP_TEST
int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "--help")) {
    puts("BSOD companion: paired Codex task details or local touch "
         "interactions. MENU header opens connection controls. Tap a resting "
         "pet to wake it. MENU offers TREAT, "
         "PLAY, REST/WAKE. Interactions "
         "auto-save. HELP explains care. RESET asks confirmation. BACK TO APPS "
         "saves and exits. HOME is owned by launcher; forced stop skips new "
         "writes.");
    return 0;
  }
  if (argc == 2 && !strcmp(argv[1], "--version")) {
    puts(HB_PET_VERSION);
    return 0;
  }
  if (argc != 1)
    return 64;
  return pet_run(argv[0]);
}
#endif
