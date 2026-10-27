#ifndef HB_EMULATOR_PLATFORM_H
#define HB_EMULATOR_PLATFORM_H
#include "../../native/linux_devices.h"
#include <stdint.h>
enum {
  EP_RIGHT = 1,
  EP_LEFT = 2,
  EP_UP = 4,
  EP_DOWN = 8,
  EP_A = 16,
  EP_B = 32,
  EP_SELECT = 64,
  EP_START = 128
};
struct ep {
  struct hb_devices display;
  int keys, touching, tx, ty, start_x, start_y, dragged;
  unsigned buttons, touch_buttons, latched_buttons, touch_chord;
  int menu, exit, volume_delta;
};
extern volatile int ep_stop;
extern uint16_t ep_canvas[HB_DISPLAY_PIXELS];
uint32_t ep_now(void);
int ep_open(struct ep *);
int ep_poll(struct ep *, int);
int ep_close(struct ep *);
void ep_present(struct ep *);
void ep_clear(void);
void ep_box(int, int, int, int, uint16_t);
void ep_text(int, int, const char *, uint16_t);
void ep_title(const char *);
void ep_controls(int tama, unsigned held);
int ep_touch_choice(const struct ep *, unsigned count);
/* Fixed exposed-storage application root; no cwd/home/tmp fallback. */
int es_open(const char *id);
const char *es_root(void);
int es_read(const char *, void *, unsigned, unsigned);
int es_write(const char *, const void *, unsigned, const void *, unsigned);
int es_remove(const char *);
int es_move(const char *, const char *);
int es_rom_list(char names[64][128]);
int es_mount_matches(const char *);
#endif
