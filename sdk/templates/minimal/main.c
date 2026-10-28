#include <x1000/app.h>
struct state {
  xw_button back;
};
static const xw_rect back = {16, 366, 208, 48};
static int event(xw_app *a, void *opaque, const xw_event *e) {
  struct state *s = opaque;
  if (xw_button_event(&s->back, back, e))
    xw_request_exit(a);
  xw_redraw(a);
  return 0;
}
static void draw(xw_app *a, void *opaque) {
  struct state *s = opaque;
  xw_clear(a, xw_rgb(248, 247, 239));
  xw_fill(a, (xw_rect){0, 0, 240, 65}, xw_rgb(230, 239, 223));
  xw_text(a, 16, 24, "Hello, Walkman!", 1, xw_rgb(54, 135, 119));
  xw_text(a, 16, 118, "A small native application.", 1, xw_rgb(84, 75, 59));
  xw_text(a, 16, 150, "Made with the X1000 SDK.", 1, xw_rgb(84, 75, 59));
  xw_text(a, 16, 250,
          xw_is_preview(a) ? "PC preview - no hardware" : "Experimental JP1.11",
          1, xw_rgb(126, 120, 104));
  xw_button_draw(a, back, "Back to apps", s->back.armed);
}
const xw_program xw_application = {
    XW_API_VERSION, "@ID@", "@TITLE@", sizeof(struct state), 0, event, draw, 0};
