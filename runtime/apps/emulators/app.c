#include "platform.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifdef HB_TAMA_ID
#include "../../../third_party/tama-id/color.h"
#define APP_ID "tamagotchi-id"
#define APP_NAME "TAMAGOTCHI ID"
#else
#include "gbc_core.h"
#include "gbc_schedule.h"
#include "../../platform/pcm_output.h"
#include <errno.h>
#define APP_ID "gbc"
#define APP_NAME "GAME BOY COLOR"
#endif
#ifndef HB_TAMA_ID
static struct hb_pcm_output audio = {.dsp = -1, .mixer = -1, .volume = 35};
static int close_audio(void) {
  gb_set_audio_sink(0, 0);
  int r = hb_pcm_close(&audio);
  if (r)
    r = hb_pcm_close(&audio);
  return r;
}
static void begin_audio(void) {
  if (close_audio())
    return;
  if (!hb_pcm_start(&audio, hb_pcm_posix_ops(), &ep_stop))
    gb_set_audio_sink(hb_pcm_submit_u8, &audio);

}
#endif
static unsigned displayed_keys;
static char roms[64][128];
static unsigned page;
static int count, mode, loaded;
static char message[100];
enum { BROWSER, GAME, MENU, ERROR_SCREEN };
static void error_text(const char *s) {
  snprintf(message, sizeof message, "%s", s);
  mode = ERROR_SCREEN;
}
static void render(void) {
#ifndef HB_TAMA_ID
  static int old_mode = -1, old_enabled = -1, old_failed = -1;
  static unsigned old_keys = ~0u;
  int shell_dirty = mode != GAME || old_mode != GAME ||
      old_keys != displayed_keys || old_enabled != audio.enabled ||
      old_failed != audio.failed;
  old_mode = mode; old_keys = displayed_keys;
  old_enabled = audio.enabled; old_failed = audio.failed;
  if (shell_dirty) {
#endif
    ep_clear();
    ep_title(APP_NAME);
#ifndef HB_TAMA_ID
  }
#endif
  if (mode == GAME) {
#ifdef HB_TAMA_ID
    ep_controls(1, displayed_keys);
    const uint16_t *p = color_pixels();
    if (p && color_visible())
      for (unsigned y = 0; y < 128; y++)
        memcpy(ep_canvas + (y + 86) * 240 + 56, p + y * 128, 256);
#else
    if (shell_dirty)
      ep_controls(0, displayed_keys);
    const uint16_t *p = gb_pixels();
    for (unsigned y = 0; y < 144; y++)
      memcpy(ep_canvas + (y + 48) * 240 + 40, p + y * 160, 320);
    ep_text(18, 367,
            audio.failed    ? "AUDIO UNAVAILABLE"
            : audio.enabled ? "PCM SOUND ON"
                            : "SOUND OFF",
            audio.failed ? 0xffe0 : 0xc61e);
    if (audio.failed) {
      char detail[64];
      snprintf(detail, sizeof detail, "A8 %s E%d V%d",
               hb_pcm_stage_name(audio.fault_stage), audio.fault_code,
               audio.fault_value);
      ep_text(8, 379, detail, 0xffe0);
    }
#endif
  } else if (mode == MENU) {
    const char *items[] = {"RESUME", "SAVE AND EXIT", "RESTART - TAP TWICE",
                           "EXIT WITHOUT SAVE"};
    for (unsigned i = 0; i < 4; i++) {
      ep_box(8, 56 + (int)i * 40, 224, 34, 0x31a6);
      ep_text(16, 70 + (int)i * 40, items[i], 0xffff);
    }
#ifndef HB_TAMA_ID
    ep_box(8, 216, 224, 34, 0x31a6);
    ep_text(16, 230,
            audio.failed    ? "AUDIO RETRY"
            : audio.enabled ? "SOUND OFF"
                            : "SOUND ON",
            0xffff);
    char volume[40];
    snprintf(volume, sizeof volume, "VOLUME %u", audio.volume);
    ep_text(16, 304, volume, 0x9cf3);
    ep_box(8, 324, 104, 30, 0x31a6);
    ep_text(26, 336, "VOLUME DOWN", 0xffff);
    ep_box(128, 324, 104, 30, 0x31a6);
    ep_text(152, 336, "VOLUME UP", 0xffff);
#endif
    ep_text(8, 268, message, 0xffe0);
#ifndef HB_TAMA_ID
    if (audio.failed) {
      char detail[64];
      snprintf(detail, sizeof detail, "A8 %s E%d V%d",
               hb_pcm_stage_name(audio.fault_stage), audio.fault_code,
               audio.fault_value);
      ep_text(8, 278, detail, 0xffe0);
    }
#endif
    ep_text(8, 286, "SAVE FILES STAY ON USER STORAGE", 0x9cf3);
  } else if (mode == BROWSER) {
    if (!count) {
      ep_text(12, 90, "NO ROMS FOUND", 0xffe0);
      ep_text(12, 118, "COPY GB OR GBC FILES INTO", 0xffff);
      ep_text(12, 136, "HOMEBREW DATA GBC ROMS", 0xffff);
    }
    for (unsigned i = 0; i < 6 && page * 6 + i < (unsigned)count; i++) {
      ep_box(8, 56 + (int)i * 40, 224, 34, 0x31a6);
      ep_text(14, 70 + (int)i * 40, roms[page * 6 + i], 0xffff);
    }
    ep_box(8, 330, 100, 30, 0x31a6);
    ep_text(34, 342, "PREVIOUS", 0xffff);
    ep_box(132, 330, 100, 30, 0x31a6);
    ep_text(168, 342, "NEXT", 0xffff);
    ep_text(8, 372, "NATIVE SIZE  PCM AUDIO", 0x9cf3);
  } else {
    ep_text(12, 80, message, 0xffe0);
    ep_text(12, 112, "TAP HERE TO RETRY", 0xffff);
#ifdef HB_TAMA_ID
    ep_text(12, 144, "PLACE ID ROM IN ROMS ROM BIN", 0x9cf3);
#else
    ep_text(12, 144, "PLACE GAMES IN ROMS FOLDER", 0x9cf3);
#endif
  }
  if (mode != GAME) {
    ep_box(0, 388, 240, 44, 0x1a4b);
    ep_text(76, 406, "BACK TO APPS", 0xffff);
  }
}
static int prepare(void) {
  if (!es_open(APP_ID)) {
    error_text("USER STORAGE NOT READY");
    return 0;
  }
#ifdef HB_TAMA_ID
  if (!color_open()) {
    int s = color_status();
    color_close();
    error_text(s == COLOR_NO_ROM     ? "ROM BIN IS MISSING"
               : s == COLOR_BAD_SAVE ? "SAVE DAMAGED - KEEP BACKUP"
               : s == COLOR_BAD_ROM  ? "SUPPORTED ID ROM REQUIRED"
                                     : "CANNOT INITIALIZE EMULATOR");
    return 0;
  }
  loaded = 1;
  mode = GAME;
#else
  count = es_rom_list(roms);
  if (count < 0) {
    error_text("CANNOT READ ROMS DIRECTORY");
    return 0;
  }
  mode = BROWSER;
  page = 0;
#endif
  return 1;
}
int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "--help")) {
    puts(APP_NAME
         ": external native app. ROMs and saves in its user-storage "
         "folder. HOME or BACK TO APPS exits; MENU offers explicit "
         "save and restart. GBC uses 22050Hz stereo PCM; iD remains silent.");
    return 0;
  }
  if (argc == 2 && !strcmp(argv[1], "--selftest")) {
    if (!es_mount_matches("/dev/mtdblock/2 /contents vfat") ||
        es_mount_matches("/dev/mtdblock/0 /contents vfat") || EP_A != 16)
      return 1;
    puts("PLATFORM CONTRACT OK");
    return 0;
  }
  if (argc != 1)
    return 64;
  struct ep platform;
  mode = ERROR_SCREEN;
  message[0] = 0;
  prepare();
  render();
  if (ep_open(&platform))
    return 2;
  ep_present(&platform);
  uint32_t next = ep_now(), previous = next;
  int confirm_reset = 0;
#ifdef HB_TAMA_ID
  unsigned last_keys = 0;
#else
  struct gb_schedule schedule = {0};
#endif
  while (!ep_stop && !platform.exit && !platform.display.failed) {
#ifdef HB_TAMA_ID
    ep_poll(&platform, 1);
#else
    ep_poll(&platform, 0);
#endif
    if (ep_stop || platform.exit)
      break;
#ifndef HB_TAMA_ID
    if (platform.volume_delta) {
      int v = (int)audio.volume + platform.volume_delta;
      hb_pcm_volume(&audio, v < 0 ? 0 : (unsigned)v);
    }
    if (mode == GAME && audio.enabled && !audio.failed)
      hb_pcm_flush(&audio);
#endif
    int redraw = 0;
    if (platform.menu && mode == GAME) {
      mode = MENU;
      platform.latched_buttons = 0;
      message[0] = 0;
      confirm_reset = 0;
      redraw = 1;
#ifdef HB_TAMA_ID
      color_buttons_clear();
      last_keys = 0;
#else
      hb_pcm_pause(&audio);
#endif
    }
    platform.menu = 0;
    if (mode == MENU) {
      int choice = ep_touch_choice(&platform,
#ifdef HB_TAMA_ID
                                   4
#else
                                   5
#endif
      );
      if (choice == 0) {
        mode = GAME;
        confirm_reset = 0;
        redraw = 1;
      } else if (choice == 1) {
        int ok;
#ifdef HB_TAMA_ID
        ok = color_save();
#else
        ok = gb_save();
#endif
        if (ok)
          break;
        snprintf(message, sizeof message, "SAVE FAILED - NOT EXITING");
        redraw = 1;
      } else if (choice == 2) {
        if (!confirm_reset) {
          confirm_reset = 1;
          snprintf(message, sizeof message, "TAP RESTART AGAIN TO CONFIRM");
        } else {
#ifdef HB_TAMA_ID
          color_close();
          loaded = 0;
          if (!color_archive_snapshot()) {
            error_text("CANNOT BACK UP OLD SAVE");
          } else if (color_open()) {
            loaded = 1;
            mode = GAME;
          } else {
            color_close();
            es_move("saves/state.bak", "saves/state.sav");
            prepare();
          }
#else
          gb_reset();
          mode = GAME;
#endif
          confirm_reset = 0;
          message[0] = 0;
        }
        redraw = 1;
      } else if (choice == 3)
        break;
#ifndef HB_TAMA_ID
      else if (choice == 4) {
        if (audio.enabled && !audio.failed)
          close_audio();
        else
          begin_audio();
        redraw = 1;
      }
      if (platform.ty >= 324 && platform.ty < 354 && platform.tx >= 0) {
        int v = (int)audio.volume + (platform.tx < 120 ? -5 : 5);
        hb_pcm_volume(&audio, v < 0 ? 0 : (unsigned)v);
        redraw = 1;
      }
      if (platform.volume_delta)
        redraw = 1;
#endif
    } else if (mode == ERROR_SCREEN && platform.tx >= 0 && platform.ty < 388) {
      prepare();
      redraw = 1;
    } else if (mode == BROWSER) {
      int c = ep_touch_choice(&platform, 6);
      if (c >= 0 && page * 6 + (unsigned)c < (unsigned)count) {
#ifndef HB_TAMA_ID
        if (gb_open(roms[page * 6 + (unsigned)c])) {
          loaded = 1;
          mode = GAME;
          platform.buttons = platform.touch_buttons = platform.latched_buttons =
              0;
          begin_audio();
        } else
          error_text(gb_error());
        redraw = 1;
#endif
      } else if (platform.ty >= 330 && platform.ty < 360) {
        if (platform.tx < 120 && page)
          page--;
        else if (platform.tx >= 120 && (page + 1) * 6 < (unsigned)count)
          page++;
        redraw = 1;
      }
    }
    uint32_t now = ep_now();
#ifndef HB_TAMA_ID
    if (mode == GAME && !schedule.running)
      gb_schedule_start(&schedule, now);
    if (mode != GAME)
      schedule.running = 0;
    if (mode == GAME) {
      gb_schedule_recover(&schedule, now);
      next = schedule.next;
    }
#endif
    if (mode == GAME && (int32_t)(now - next) >= 0) {
      unsigned keys =
          platform.buttons | platform.touch_buttons | platform.latched_buttons;
      platform.latched_buttons = 0;
      displayed_keys = keys;
#ifdef HB_TAMA_ID
      if ((keys ^ last_keys) & EP_LEFT)
        color_button(0, !!(keys & EP_LEFT));
      if ((keys ^ last_keys) & EP_A)
        color_button(1, !!(keys & EP_A));
      if ((keys ^ last_keys) & EP_RIGHT)
        color_button(2, !!(keys & EP_RIGHT));
      last_keys = keys;
      uint32_t dt = now - previous;
      color_tick(dt > 32 ? 32 : dt);
      if (color_status() == COLOR_CORE_ERROR) {
        error_text("EMULATOR STOPPED - EXIT SAFELY");
      }
      next += 16;
#else
      if (!gb_frame(keys)) {
        hb_pcm_pause(&audio);
        error_text(gb_error());
      }
      gb_schedule_advance(&schedule);
      next = schedule.next;
#endif
      previous = now;
#ifdef HB_TAMA_ID
      if ((int32_t)(now - next) > 100)
        next = now;
      redraw = 1;
#else
      /* Catch up audio before spending time on presentation. Never skip CPU/APU. */
      redraw = mode != GAME || (audio.failed && redraw) || gb_schedule_present(&schedule, ep_now());
#endif
    } else if (mode != GAME) {
      next = previous = now;
    }
    if (redraw) {
      render();
#ifndef HB_TAMA_ID
      if (mode == GAME && audio.enabled && !audio.failed)
        hb_pcm_flush(&audio);
#endif
      ep_present(&platform);
    }
    hb_devices_flush(&platform.display);
    if ((int32_t)(next - ep_now()) > 1 || mode != GAME)
      usleep(1000);
  }
#ifdef HB_TAMA_ID
  color_close();
#else
  int audio_failure = close_audio();
  gb_close();
#endif
  (void)loaded;
  int display_failure = ep_close(&platform);
#ifndef HB_TAMA_ID
  if (audio_failure)
    return 2;
#endif
  return display_failure ? 2 : 0;
}
