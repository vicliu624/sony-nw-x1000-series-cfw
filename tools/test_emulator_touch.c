#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
static unsigned char input[11];
static int pending;
int open(const char *p, int flags, ...) {
  assert(!strcmp(p, "/dev/input/event0") && flags == (O_RDONLY | O_NONBLOCK));
  errno = ENOENT;
  return -1;
}
int hb_stop_signals_install(volatile int *p) {
  *p = 0;
  return 0;
}
int hb_devices_open(struct hb_devices *d, const unsigned short *p, unsigned n,
                    volatile int *s) {
  (void)p;
  assert(n == 240 * 432);
  memset(d, 0, sizeof(*d));
  d->stop = s;
  return 0;
}
int hb_devices_close(struct hb_devices *d) {
  (void)d;
  return 0;
}
void hb_devices_present(struct hb_devices *d) { (void)d; }
int hb_devices_next_touch(struct hb_devices *d, unsigned char p[11], int ms) {
  (void)d;
  assert(!ms);
  if (!pending)
    return 0;
  memcpy(p, input, 11);
  pending = 0;
  return 1;
}
static void point(struct ep *p, int tama, int x, int y, int down) {
  unsigned rx = (x * 2929 + 239) / 240, ry = ((431 - y) * 5281 + 431) / 432;
  memset(input, 0, sizeof input);
  input[1] = down;
  input[2] = rx >> 8;
  input[3] = rx;
  input[4] = ry >> 8;
  input[5] = ry;
  pending = 1;
  assert(!ep_poll(p, tama));
}
int main(void) {
  struct ep p;
  assert(!ep_open(&p));
  struct {
    int x, y;
    unsigned key;
  } cases[] = {{60, 250, EP_UP},      {24, 282, EP_LEFT},  {98, 282, EP_RIGHT},
               {60, 320, EP_DOWN},    {162, 274, EP_B},    {210, 242, EP_A},
               {152, 334, EP_SELECT}, {204, 334, EP_START}};
  for (unsigned i = 0; i < 8; i++) {
    p.latched_buttons = 0;
    point(&p, 0, cases[i].x, cases[i].y, 1);
    assert(p.touch_buttons == cases[i].key);
    point(&p, 0, cases[i].x, cases[i].y, 0);
    assert(p.touch_buttons == 0 && p.latched_buttons == cases[i].key);
  }
  for (unsigned i = 0; i < 3; i++) {
    p.latched_buttons = 0;
    point(&p, 1, 48 + i * 72, 294, 1);
    assert(p.touch_buttons == (i == 0 ? EP_LEFT : i == 1 ? EP_A : EP_RIGHT));
    point(&p, 1, 48 + i * 72, 294, 0);
    assert(!p.touch_buttons && p.latched_buttons);
  }
  point(&p, 0, 210, 242, 1);
  point(&p, 0, 24, 282, 1);
  assert(p.touch_buttons == (EP_A | EP_LEFT));
  point(&p, 0, 24, 282, 0);
  assert(!p.touch_buttons && !p.touch_chord);
  point(&p, 0, 80, 100, 1);
  point(&p, 0, 100, 410, 0);
  assert(!p.exit);
  point(&p, 0, 210, 12, 1);
  point(&p, 0, 210, 12, 0);
  assert(p.menu);
  p.menu = 0;
  point(&p, 0, 110, 410, 1);
  point(&p, 0, 110, 410, 0);
  assert(p.exit);
  assert(!ep_close(&p));
  puts("8 GBC and 3 iD touch buttons, quick-tap latching, A+direction drag, "
       "menu, cancel-drag and return passed");
  return 0;
}
