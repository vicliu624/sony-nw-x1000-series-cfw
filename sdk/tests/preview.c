/* Actual SDL window/renderer/input loop, using the dummy video driver in CI. */
#include "../../runtime/platform/sdk/internal.h"
#include <SDL2/SDL.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned downs, ups, finishes;
static int init(xw_app *app, void *state) {
  SDL_Event event;
  (void)app;
  (void)state;
  SDL_zero(event);
  event.type = SDL_MOUSEBUTTONDOWN;
  event.button.button = SDL_BUTTON_LEFT;
  event.button.x = 60;
  event.button.y = 215;
  assert(SDL_PushEvent(&event) == 1);
  event.type = SDL_MOUSEBUTTONUP;
  assert(SDL_PushEvent(&event) == 1);
  SDL_zero(event);
  event.type = SDL_QUIT;
  assert(SDL_PushEvent(&event) == 1);
  return 0;
}
static int input(xw_app *app, void *state, const xw_event *event) {
  (void)state;
  if (event->type == XW_TOUCH_DOWN || event->type == XW_TOUCH_UP) {
    assert(event->x >= 0 && event->x < 240 && event->y >= 0 && event->y < 432);
  }
  if (event->type == XW_TOUCH_DOWN)
    downs++;
  if (event->type == XW_TOUCH_UP)
    ups++;
  xw_redraw(app);
  return 0;
}
static void draw(xw_app *app, void *state) {
  (void)state;
  xw_clear(app, xw_rgb(54, 135, 119));
}
static int finish(xw_app *app, void *state) {
  (void)app;
  (void)state;
  finishes++;
  return 0;
}
int main(void) {
  const xw_program program = {
      1, "preview-test", "SDK preview test", 0, init, input, draw, finish};
  xw_app *app = calloc(1, sizeof(*app));
  assert(app);
  app->preview = 1;
  assert(!xw_run(app, &program, &xw_host_backend));
  assert(downs == 1 && ups == 1 && finishes == 1);
  assert(!app->backend_state);
  free(app);
  puts("SDL preview opens, presents, processes touch, exits and cleans up");
  return 0;
}
