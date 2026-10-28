#include "../../native/frontend.h"
#include "../../native/linux_devices.h"
#include "../../store/deadline.h"
#include "../../store/termination.h"
#include "internal.h"
#include <signal.h>
#include <stdlib.h>
typedef void (*sdk_handler)(int);
extern sdk_handler sdk_signal(int, sdk_handler) __asm__("signal");
static volatile int *interrupt_flag;
static void interrupt(int number) {
  (void)number;
  if (interrupt_flag)
    *interrupt_flag = 1;
}
struct native_state {
  struct hb_devices devices;
  int signals, int_signal;
  sdk_handler previous_int;
  unsigned long long last;
};
static int native_open(xw_app *a) {
  struct native_state *s = calloc(1, sizeof(*s));
  if (!s)
    return -1;
  a->backend_state = s;
  s->devices.fb = s->devices.touch = -1;
  if (hb_store_termination_begin())
    return -1;
  s->signals = 1;
  interrupt_flag = hb_store_termination_flag();
  s->previous_int = sdk_signal(SIGINT, interrupt);
  if (s->previous_int == SIG_ERR)
    return -1;
  s->int_signal = 1;
  if (hb_monotonic_millis(&s->last))
    return -1;
  /* The launcher retains its HOME observer and sends SIGTERM to the child
   * group. Do not create a competing read of the same HOME event stream. */
  return hb_devices_open(&s->devices, a->pixels, XW_WIDTH * XW_HEIGHT,
                         hb_store_termination_flag());
}
static int native_next(xw_app *a, xw_event *e) {
  struct native_state *s = a->backend_state;
  unsigned char packet[11];
  unsigned long long now;
  if (*hb_store_termination_flag()) {
    e->type = XW_STOP;
    e->reason = XW_SIGNAL;
    return 1;
  }
  hb_devices_flush(&s->devices);
  if (s->devices.failed)
    return -1;
  int got = hb_devices_next_touch(&s->devices, packet, 33);
  if (got == -1) {
    e->type = XW_STOP;
    e->reason = XW_SIGNAL;
    return 1;
  }
  if (got < 0)
    return -1;
  if (hb_monotonic_millis(&now) || now < s->last)
    return -1;
  e->elapsed_ms = now - s->last > 1000 ? 1000 : (unsigned)(now - s->last);
  s->last = now;
  if (!got) {
    e->type = XW_TICK;
    return 1;
  }
  struct hb_touch touch;
  hb_touch_decode(packet, &touch);
  e->x = touch.in_bounds ? (int)touch.x : -1;
  e->y = touch.in_bounds ? (int)touch.y : -1;
  e->type =
      touch.down ? (a->pressed ? XW_TOUCH_MOVE : XW_TOUCH_DOWN) : XW_TOUCH_UP;
  a->pressed = touch.down;
  return 1;
}
static int native_present(xw_app *a) {
  struct native_state *s = a->backend_state;
  hb_devices_present(&s->devices);
  return s->devices.failed ? -1 : 0;
}
static int native_close(xw_app *a) {
  struct native_state *s = a->backend_state;
  int rc = 0;
  if (!s)
    return 0;
  if (hb_devices_close(&s->devices))
    rc = -1;
  if (s->int_signal && sdk_signal(SIGINT, s->previous_int) == SIG_ERR)
    rc = -1;
  interrupt_flag = 0;
  if (s->signals && hb_store_termination_end())
    rc = -1;
  free(s);
  a->backend_state = 0;
  return rc;
}
const struct xw_backend xw_native_backend = {native_open, native_next,
                                             native_present, native_close};
