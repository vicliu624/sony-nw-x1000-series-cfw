#include "platform.h"
#include "../../native/font.inc"
#include "../../native/frontend.h"
#include "../../native/linux_signals.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
volatile int ep_stop;
uint16_t ep_canvas[HB_DISPLAY_PIXELS];
extern int ep_gettimeofday(void *, void *) __asm__("gettimeofday");
uint32_t ep_now(void) {
  int32_t t[2];
  if (ep_gettimeofday(t, 0))
    return 0;
  return (uint32_t)t[0] * 1000u + (unsigned)t[1] / 1000;
}
void ep_box(int x, int y, int w, int h, uint16_t c) {
  for (int j = y; j < y + h; j++)
    for (int i = x; i < x + w; i++)
      if (i >= 0 && i < 240 && j >= 0 && j < 432)
        ep_canvas[j * 240 + i] = c;
}
void ep_text(int x, int y, const char *s, uint16_t c) {
  for (; *s && x < 234; s++, x += 6) {
    int ch = (unsigned char)*s;
    if (ch >= 'a' && ch <= 'z')
      ch -= 32;
    int g = ch >= '0' && ch <= '9'   ? ch - '0'
            : ch >= 'A' && ch <= 'Z' ? ch - 'A' + 10
                                     : -1;
    if (g >= 0) {
      for (int j = 0; j < 7; j++)
        for (int i = 0; i < 5; i++)
          if (glyph[g][j] & (1 << (4 - i)))
            ep_box(x + i, y + j, 1, 1, c);
    } else if (ch != ' ')
      ep_box(x, y + 3, 3, 1, c);
  }
}
void ep_clear(void) { ep_box(0, 0, 240, 432, 0x0843); }
void ep_title(const char *s) {
  ep_box(0, 0, 240, 28, 0x1a4b);
  ep_text(8, 10, s, 0xffff);
  ep_box(190, 0, 50, 28, 0x39c7);
  ep_text(202, 10, "MENU", 0xffff);
}
static void ellipse(int cx, int cy, int rx, int ry, uint16_t c) {
  for (int y = -ry; y <= ry; y++)
    for (int x = -rx; x <= rx; x++)
      if ((long long)x * x * ry * ry + (long long)y * y * rx * rx <=
          (long long)rx * rx * ry * ry)
        ep_box(cx + x, cy + y, 1, 1, c);
}
static void roundbox(int x, int y, int w, int h, int r, uint16_t c) {
  ep_box(x + r, y, w - 2 * r, h, c);
  ep_box(x, y + r, w, h - 2 * r, c);
  ellipse(x + r, y + r, r, r, c);
  ellipse(x + w - r - 1, y + r, r, r, c);
  ellipse(x + r, y + h - r - 1, r, r, c);
  ellipse(x + w - r - 1, y + h - r - 1, r, r, c);
}
static void button(int x, int y, int r, const char *label, int down,
                   uint16_t c) {
  ellipse(x + 1, y + 3, r + 2, r + 2, 0x20a3);
  ellipse(x, y, r + 1, r + 1, 0x39a7);
  ellipse(x, y + (down ? 2 : 0), r - 1, r - 1, down ? 0x6b6d : c);
  ep_text(x - (int)strlen(label) * 3, y - 3 + (down ? 2 : 0), label, 0xffff);
}
void ep_controls(int tama, unsigned held) {
  if (tama) {
    roundbox(9, 34, 224, 347, 20, 0x22eb);
    roundbox(6, 30, 224, 347, 20, 0x4d74);
    roundbox(11, 34, 214, 339, 17, 0x86da);
    roundbox(26, 48, 188, 184, 12, 0x1966);
    ep_text(86, 65, "COLOR LCD", 0x9492);
    ep_box(56, 86, 128, 128, 0x18c3);
    ep_text(81, 241, "TAMAGOTCHI ID", 0x1269);
    for (int i = 0; i < 3; i++) {
      unsigned mask = i == 0 ? EP_LEFT : i == 1 ? EP_A : EP_RIGHT;
      int down = !!(held & mask);
      int x = 48 + i * 72;
      button(x, 294, 28, i == 0 ? "A" : i == 1 ? "B" : "C", down, 0x296b);
      if (!down)
        ellipse(x - 7, 284, 11, 4, 0x4a73);
    }
    for (int i = 0; i < 4; i++)
      ep_box(170 + i * 11, 354, 5, 9, 0x2bad);
  } else {
    roundbox(9, 34, 224, 347, 20, 0x2085);
    roundbox(6, 30, 224, 347, 20, 0x5192);
    roundbox(11, 34, 214, 339, 17, 0x7257);
    roundbox(26, 38, 188, 166, 12, 0x20a4);
    ep_box(40, 48, 160, 144, 0);
    ep_text(68, 209, "GAME BOY COLOR", 0xc61e);
    ep_box(42, 235, 40, 101, 0x18a3);
    ep_box(10, 266, 104, 40, 0x18a3);
    ep_box(46, 239, 32, 93, 0x39c7);
    ep_box(14, 270, 96, 32, 0x39c7);
    if (held & EP_UP)
      ep_box(46, 239, 32, 27, 0x7bcf);
    if (held & EP_DOWN)
      ep_box(46, 306, 32, 26, 0x7bcf);
    if (held & EP_LEFT)
      ep_box(14, 270, 28, 32, 0x7bcf);
    if (held & EP_RIGHT)
      ep_box(82, 270, 28, 32, 0x7bcf);
    ep_text(56, 248, "UP", 0xd69a);
    ep_text(51, 318, "DOWN", 0xd69a);
    ep_text(20, 282, "L", 0xd69a);
    ep_text(98, 282, "R", 0xd69a);
    button(162, 274, 21, "B", !!(held & EP_B), 0x296b);
    button(210, 242, 21, "A", !!(held & EP_A), 0x296b);
    roundbox(126, 324, 52, 20, 8, (held & EP_SELECT) ? 0x7bcf : 0x2945);
    roundbox(182, 324, 44, 20, 8, (held & EP_START) ? 0x7bcf : 0x2945);
    ep_text(134, 330, "SELECT", 0xffff);
    ep_text(189, 330, "START", 0xffff);
    for (int i = 0; i < 4; i++)
      ep_box(170 + i * 11, 354, 5, 9, 0x390c);
  }
  ep_box(0, 388, 240, 44, 0x1a4b);
  ep_text(76, 406, "BACK TO APPS", 0xffff);
}

int ep_open(struct ep *p) {
  memset(p, 0, sizeof(*p));
  p->keys = -1;
  ep_stop = 0;
  if (hb_stop_signals_install(&ep_stop))
    return -1;
  p->keys = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
  if (p->keys >= 0) {
    extern int ep_fcntl(int, int, ...) __asm__("fcntl");
    if (ep_fcntl(p->keys, F_SETFD, FD_CLOEXEC) < 0) {
      close(p->keys);
      p->keys = -1;
    }
  }
  if (hb_devices_open(&p->display, ep_canvas, HB_DISPLAY_PIXELS, &ep_stop)) {
    if (p->keys >= 0)
      close(p->keys);
    return -1;
  }
  return 0;
}
static unsigned touch_button(int x, int y) {
  for (int i = 0; i < 3; i++) {
    int dx = x - (48 + i * 72), dy = y - 294;
    if (dx * dx + dy * dy <= 34 * 34)
      return i == 0 ? EP_LEFT : i == 1 ? EP_A : EP_RIGHT;
  }
  return 0;
}

int ep_poll(struct ep *p, int tama) {
  p->tx = p->ty = -1;
  p->volume_delta = 0;
  if (p->keys >= 0) {
    unsigned char packets[16 * 16];
    for (unsigned n = 0; n < 4; n++) {
      ssize_t got = read(p->keys, packets, sizeof packets);
      if (got < 0 && (errno == EAGAIN || errno == EINTR))
        break;
      if (got <= 0 || got % 16) {
        close(p->keys);
        p->keys = -1;
        break;
      }
      for (unsigned i = 0; i < (unsigned)got; i += 16) {
        unsigned char *b = packets + i;
        unsigned type = b[8] | (b[9] << 8), code = b[10] | (b[11] << 8),
                 v = b[12] | (b[13] << 8) | (b[14] << 16) | (b[15] << 24);
        if (type != 1)
          continue;
        if (!tama && (code == 16 || code == 17)) {
          if (v == 1 || v == 2)
            p->volume_delta += code == 17 ? 5 : -5;
          continue;
        }
        if (code == 18 && v == 1)
          p->exit = 1;
        unsigned k = code == 1    ? EP_RIGHT
                     : code == 2  ? EP_LEFT
                     : code == 17 ? EP_UP
                     : code == 16 ? EP_DOWN
                     : code == 0  ? EP_A
                                  : 0;
        if (v == 1) {
          p->buttons |= k;
          p->latched_buttons |= k;
        } else if (v == 0)
          p->buttons &= ~k;
      }
    }
  }
  unsigned char raw[11];
  int got = hb_devices_next_touch(&p->display, raw, 0);
  if (got < 0) {
    if (!ep_stop)
      p->exit = 1;
    return -1;
  }
  if (got) {
    struct hb_touch t;
    hb_touch_decode(raw, &t);
    p->touch_buttons = 0;
    if (t.down) {
      if (!p->touching) {
        p->start_x = (int)t.x;
        p->start_y = (int)t.y;
        p->dragged = 0;
        p->touch_chord = 0;
      } else if ((int)t.x - p->start_x > 12 || p->start_x - (int)t.x > 12 ||
                 (int)t.y - p->start_y > 12 || p->start_y - (int)t.y > 12)
        p->dragged = 1;
      p->touching = 1;
      if (t.in_bounds) {
        int x = (int)t.x, y = (int)t.y;
        if (tama)
          p->touch_buttons = touch_button(x, y);
        else if (x >= 42 && x < 82 && y >= 235 && y < 266)
          p->touch_buttons = EP_UP;
        else if (x < 42 && y >= 266 && y < 306)
          p->touch_buttons = EP_LEFT;
        else if (x >= 82 && x < 116 && y >= 266 && y < 306)
          p->touch_buttons = EP_RIGHT;
        else if (x >= 42 && x < 82 && y >= 306 && y < 338)
          p->touch_buttons = EP_DOWN;
        else if (x >= 142 && x < 184 && y >= 248 && y < 296)
          p->touch_buttons = EP_B;
        else if (x >= 188 && y >= 218 && y < 268)
          p->touch_buttons = EP_A;
        else if (x >= 130 && x < 180 && y >= 320 && y < 350)
          p->touch_buttons = EP_SELECT;
        else if (x >= 184 && y >= 320 && y < 350)
          p->touch_buttons = EP_START;
        if (!tama && !p->dragged && (p->touch_buttons & (EP_A | EP_B)))
          p->touch_chord = p->touch_buttons & (EP_A | EP_B);
        p->touch_buttons |= p->touch_chord;
        p->latched_buttons |= p->touch_buttons;
      }
    } else if (p->touching) {
      p->touching = 0;
      p->touch_chord = 0;
      if ((int)t.x - p->start_x > 12 || p->start_x - (int)t.x > 12 ||
          (int)t.y - p->start_y > 12 || p->start_y - (int)t.y > 12)
        p->dragged = 1;
      if (t.in_bounds && !p->dragged) {
        p->tx = (int)t.x;
        p->ty = (int)t.y;
        if (t.y >= 388)
          p->exit = 1;
        if (t.y < 28 && t.x >= 190)
          p->menu = 1;
      }
    }
  }
  return 0;
}
int ep_touch_choice(const struct ep *p, unsigned count) {
  return p->tx >= 0 && p->ty >= 56 && p->ty < 56 + (int)count * 40
             ? (p->ty - 56) / 40
             : -1;
}
void ep_present(struct ep *p) { hb_devices_present(&p->display); }
int ep_close(struct ep *p) {
  int r = hb_devices_close(&p->display);
  if (p->keys >= 0 && close(p->keys))
    r = -1;
  p->keys = -1;
  return r;
}
