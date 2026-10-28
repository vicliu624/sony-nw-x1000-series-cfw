#include "internal.h"
#include <stdlib.h>
#include <string.h>
#ifndef XW_SDK_VERSION
#define XW_SDK_VERSION "unversioned"
#endif
const char *xw_sdk_version(void) { return XW_SDK_VERSION; }
int xw_id_valid(const char *s) {
  unsigned n = 0;
  if (!s || !*s || *s == '-')
    return 0;
  for (; s[n]; n++)
    if (n >= 32 || !((s[n] >= 'a' && s[n] <= 'z') ||
                     (s[n] >= '0' && s[n] <= '9') || s[n] == '-'))
      return 0;
  return 1;
}
void xw_request_exit(xw_app *a) {
  if (a)
    a->stop = 1;
}
void xw_redraw(xw_app *a) {
  if (a)
    a->dirty = 1;
}
int xw_is_stopping(const xw_app *a) { return !a || a->stop; }
int xw_is_preview(const xw_app *a) { return a && a->preview; }
int xw_run(xw_app *a, const xw_program *p, const struct xw_backend *b) {
  void *state;
  int result = 0, initialized = 0, opened = 0;
  if (!a || !p || !b || !b->open || !b->next || !b->present || !b->close ||
      p->api != XW_API_VERSION || !xw_id_valid(p->id) || !p->title ||
      !p->draw || p->state_bytes > 65536)
    return 64;
  a->program = p;
  a->dirty = 1;
  a->clip = (xw_rect){0, 0, XW_WIDTH, XW_HEIGHT};
  state = calloc(1, p->state_bytes ? p->state_bytes : 1);
  if (!state)
    return 70;
  opened = 1; /* close must handle partially opened backends. */
  if (b->open(a)) {
    result = 74;
    goto done;
  }
  initialized = 1;
  if (p->init && p->init(a, state)) {
    result = 70;
    goto done;
  }
  while (!a->stop) {
    xw_event e;
    int got;
    if (a->dirty) {
      a->dirty = 0;
      p->draw(a, state);
      if (b->present(a)) {
        result = 74;
        a->reason = XW_DEVICE_ERROR;
        break;
      }
    }
    if (a->stop)
      break;
    memset(&e, 0, sizeof e);
    got = b->next(a, &e);
    if (got < 0) {
      result = 74;
      a->reason = XW_DEVICE_ERROR;
      break;
    }
    if (!got)
      continue;
    if (e.type == XW_STOP) {
      a->reason = e.reason;
      a->stop = 1;
      if (e.reason == XW_DEVICE_ERROR)
        result = 74;
    }
    if (p->event && p->event(a, state, &e)) {
      result = 70;
      break;
    }
  }
done:
  a->stop = 1;
  if (initialized && p->finish && p->finish(a, state))
    result = 74;
  if (opened && b->close(a))
    result = 74;
  free(state);
  return result;
}
int xw_button_event(xw_button *b, xw_rect r, const xw_event *e) {
  int inside, fired = 0;
  if (!b || !e || r.width <= 0 || r.height <= 0)
    return 0;
  inside = e->x >= r.x && e->y >= r.y &&
           (long long)e->x < (long long)r.x + r.width &&
           (long long)e->y < (long long)r.y + r.height;
  if (e->type == XW_TOUCH_DOWN) {
    b->armed = inside;
    b->cancelled = 0;
    b->x = e->x;
    b->y = e->y;
  }
  if (b->armed && (e->type == XW_TOUCH_MOVE || e->type == XW_TOUCH_UP)) {
    long long dx = (long long)e->x - b->x, dy = (long long)e->y - b->y;
    if (dx > 12 || dx < -12 || dy > 12 || dy < -12 || !inside)
      b->cancelled = 1;
  }
  if (e->type == XW_TOUCH_UP) {
    fired = b->armed && !b->cancelled && inside;
    b->armed = 0;
  }
  if (e->type == XW_STOP)
    b->armed = 0;
  return fired;
}
