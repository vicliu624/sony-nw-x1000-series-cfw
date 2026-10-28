#include <stdio.h>
#include <x1000/app.h>
#include <x1000/storage.h>
struct state {
  xw_button count_button, back;
  unsigned count;
  int storage;
};
static const xw_rect increment = {16, 190, 208, 58}, back = {16, 366, 208, 48};
static int init(xw_app *a, void *opaque) {
  struct state *s = opaque;
  unsigned char value[4];
  size_t size = 0;
  s->storage = xw_data_read(a, "counter.bin", value, sizeof value, &size);
  if (!s->storage && size == 4)
    s->count = (unsigned)value[0] | ((unsigned)value[1] << 8) |
               ((unsigned)value[2] << 16) | ((unsigned)value[3] << 24);
  if (!s->storage && size != 4)
    s->storage = XW_STORAGE_INVALID;
  return 0; /* Missing/locked storage is visible, never a system-path fallback.
             */
}
static int event(xw_app *a, void *opaque, const xw_event *e) {
  struct state *s = opaque;
  if (xw_button_event(&s->count_button, increment, e)) {
    if (s->count < 999999)
      s->count++;
    unsigned char value[4] = {
        (unsigned char)s->count, (unsigned char)(s->count >> 8),
        (unsigned char)(s->count >> 16), (unsigned char)(s->count >> 24)};
    s->storage = xw_data_write(a, "counter.bin", value, sizeof value);
  }
  if (xw_button_event(&s->back, back, e))
    xw_request_exit(a);
  if (e->type != XW_TICK)
    xw_redraw(a);
  return 0;
}
static void draw(xw_app *a, void *opaque) {
  struct state *s = opaque;
  char value[40];
  xw_clear(a, xw_rgb(248, 247, 239));
  xw_fill(a, (xw_rect){0, 0, 240, 65}, xw_rgb(230, 239, 223));
  xw_text(a, 16, 24, "Pocket counter", 1, xw_rgb(54, 135, 119));
  snprintf(value, sizeof value, "%u", s->count);
  xw_text(a, 25, 110, value, 3, xw_rgb(84, 75, 59));
  xw_button_draw(a, increment, "Add one", s->count_button.armed);
  xw_text(a, 16, 277,
          s->storage == 0                    ? "Settings saved"
          : s->storage == XW_STORAGE_MISSING ? "No settings yet"
                                             : "Storage unavailable",
          1, xw_rgb(126, 120, 104));
  xw_text(a, 16, 305,
          xw_is_preview(a) ? "Host files only" : "USB ownership must be proven",
          1, xw_rgb(126, 120, 104));
  xw_button_draw(a, back, "Back to apps", s->back.armed);
}
const xw_program xw_application = {XW_API_VERSION,
                                   "sdk-counter",
                                   "Pocket Counter",
                                   sizeof(struct state),
                                   init,
                                   event,
                                   draw,
                                   0};
