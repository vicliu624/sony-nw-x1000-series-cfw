#include <x1000/app.h>
struct state {
  xw_button back;
  unsigned ms;
  int x, direction;
};
static const xw_rect back = {16, 366, 208, 48};
static int init(xw_app *a, void *opaque) {
  struct state *s = opaque;
  (void)a;
  s->x = 20;
  s->direction = 1;
  return 0;
}
static int event(xw_app *a, void *opaque, const xw_event *e) {
  struct state *s = opaque;
  if (e->elapsed_ms) {
    s->ms += e->elapsed_ms;
    while (s->ms >= 16) {
      s->ms -= 16;
      s->x += s->direction * 2;
      if (s->x >= 192) {
        s->x = 192;
        s->direction = -1;
      }
      if (s->x <= 16) {
        s->x = 16;
        s->direction = 1;
      }
    }
    xw_redraw(a);
  }
  if (e->type == XW_TOUCH_UP && e->y < 340) {
    s->direction = -s->direction;
    xw_redraw(a);
  }
  if (xw_button_event(&s->back, back, e))
    xw_request_exit(a);
  return 0;
}
static void draw(xw_app *a, void *opaque) {
  struct state *s = opaque;
  xw_clear(a, xw_rgb(248, 247, 239));
  xw_fill(a, (xw_rect){0, 0, 240, 65}, xw_rgb(230, 239, 223));
  xw_text(a, 16, 24, "Canvas playground", 1, xw_rgb(54, 135, 119));
  xw_clip(a, (xw_rect){16, 90, 208, 235});
  xw_fill(a, (xw_rect){0, 90, 240, 235}, xw_rgb(232, 235, 218));
  xw_fill(a, (xw_rect){s->x, 180, 32, 32}, xw_rgb(54, 135, 119));
  xw_reset_clip(a);
  xw_text(a, 16, 337, "Tap the canvas to turn.", 1, xw_rgb(84, 75, 59));
  xw_button_draw(a, back, "Back to apps", s->back.armed);
}
const xw_program xw_application = {
    XW_API_VERSION, "@ID@", "@TITLE@", sizeof(struct state),
    init,           event,  draw,      0};
