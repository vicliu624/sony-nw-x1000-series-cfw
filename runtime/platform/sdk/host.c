/* PC-only SDL preview and deterministic event replay. Never linked to ARM. */
#include "internal.h"
#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct host_state {
  SDL_Window *window;
  SDL_Renderer *renderer;
  SDL_Texture *texture;
  FILE *events;
  unsigned last, commands;
  int initialized, pending, x, y;
};
static int host_open(xw_app *a) {
  struct host_state *s = calloc(1, sizeof(*s));
  if (!s)
    return -1;
  a->backend_state = s;
  if (a->render_path) {
    if (a->event_path) {
      s->events = fopen(a->event_path, "r");
      if (!s->events)
        return -1;
    }
    return 0;
  }
  if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER))
    return -1;
  s->initialized = 1;
  s->window =
      SDL_CreateWindow(a->program->title, SDL_WINDOWPOS_CENTERED,
                       SDL_WINDOWPOS_CENTERED, 480, 864, SDL_WINDOW_SHOWN);
  if (!s->window)
    return -1;
  s->renderer = SDL_CreateRenderer(s->window, -1, SDL_RENDERER_SOFTWARE);
  if (!s->renderer)
    return -1;
  SDL_RenderSetLogicalSize(s->renderer, XW_WIDTH, XW_HEIGHT);
  s->texture =
      SDL_CreateTexture(s->renderer, SDL_PIXELFORMAT_RGB565,
                        SDL_TEXTUREACCESS_STREAMING, XW_WIDTH, XW_HEIGHT);
  s->last = SDL_GetTicks();
  return s->texture ? 0 : -1;
}
static int host_next(xw_app *a, xw_event *e) {
  struct host_state *s = a->backend_state;
  if (a->render_path) {
    char line[128], word[32], tail;
    int x = 0, y = 0;
    unsigned ms = 0;
    if (s->pending) {
      s->pending = 0;
      e->type = XW_TOUCH_UP;
      e->x = s->x;
      e->y = s->y;
      return 1;
    }
    if (!s->events || !fgets(line, sizeof(line), s->events)) {
      e->type = XW_STOP;
      return 1;
    }
    if (++s->commands > 10000 || !strchr(line, '\n') ||
        sscanf(line, "%31s", word) != 1)
      return -1;
    if (!strcmp(word, "tap") || !strcmp(word, "down") ||
        !strcmp(word, "move") || !strcmp(word, "up")) {
      if (sscanf(line, "%31s %d %d %c", word, &x, &y, &tail) != 3 || x < 0 ||
          x >= XW_WIDTH || y < 0 || y >= XW_HEIGHT)
        return -1;
      e->x = x;
      e->y = y;
      e->type = !strcmp(word, "move") ? XW_TOUCH_MOVE
                : !strcmp(word, "up") ? XW_TOUCH_UP
                                      : XW_TOUCH_DOWN;
      if (!strcmp(word, "tap")) {
        s->pending = 1;
        s->x = x;
        s->y = y;
      }
    } else if (!strcmp(word, "tick")) {
      if (sscanf(line, "%31s %u %c", word, &ms, &tail) != 2 || ms > 1000)
        return -1;
      e->type = XW_TICK;
      e->elapsed_ms = ms;
    } else {
      if (sscanf(line, "%31s %c", word, &tail) != 1)
        return -1;
      e->type = XW_STOP;
      e->reason = !strcmp(word, "home")    ? XW_HOME
                  : !strcmp(word, "usb")   ? XW_USB
                  : !strcmp(word, "fault") ? XW_DEVICE_ERROR
                                           : XW_EXIT_REQUESTED;
      if (strcmp(word, "home") && strcmp(word, "usb") &&
          strcmp(word, "fault") && strcmp(word, "stop"))
        return -1;
    }
    return 1;
  }
  SDL_Event event;
  if (!SDL_WaitEventTimeout(&event, 33)) {
    e->type = XW_TICK;
  } else if (event.type == SDL_QUIT) {
    e->type = XW_STOP;
  } else if (event.type == SDL_KEYDOWN &&
             (event.key.keysym.sym == SDLK_ESCAPE ||
              event.key.keysym.sym == SDLK_HOME)) {
    e->type = XW_STOP;
    e->reason = XW_HOME;
  } else if (event.type == SDL_MOUSEBUTTONDOWN ||
             event.type == SDL_MOUSEBUTTONUP || event.type == SDL_MOUSEMOTION) {
    if (event.type == SDL_MOUSEMOTION && !a->pressed)
      return 0;
    if (event.type != SDL_MOUSEMOTION && event.button.button != SDL_BUTTON_LEFT)
      return 0;
    e->type = event.type == SDL_MOUSEBUTTONDOWN ? XW_TOUCH_DOWN
              : event.type == SDL_MOUSEBUTTONUP ? XW_TOUCH_UP
                                                : XW_TOUCH_MOVE;
    e->x = event.type == SDL_MOUSEMOTION ? event.motion.x : event.button.x;
    e->y = event.type == SDL_MOUSEMOTION ? event.motion.y : event.button.y;
    a->pressed = e->type != XW_TOUCH_UP;
  } else
    return 0;
  unsigned now = SDL_GetTicks();
  e->elapsed_ms = now - s->last > 1000 ? 1000 : now - s->last;
  s->last = now;
  return 1;
}
static int host_present(xw_app *a) {
  struct host_state *s = a->backend_state;
  if (a->render_path) {
    FILE *f = fopen(a->render_path, "wb");
    if (!f)
      return -1;
    int rc = fprintf(f, "P6\n%d %d\n255\n", XW_WIDTH, XW_HEIGHT) < 0 ? -1 : 0;
    for (unsigned i = 0; !rc && i < XW_WIDTH * XW_HEIGHT; i++) {
      unsigned c = a->pixels[i];
      unsigned char rgb[3] = {(unsigned char)(((c >> 11) & 31) * 255 / 31),
                              (unsigned char)(((c >> 5) & 63) * 255 / 63),
                              (unsigned char)((c & 31) * 255 / 31)};
      if (fwrite(rgb, 1, 3, f) != 3)
        rc = -1;
    }
    if (fclose(f))
      rc = -1;
    return rc;
  }
  return SDL_UpdateTexture(s->texture, 0, a->pixels, XW_WIDTH * 2) ||
                 SDL_RenderClear(s->renderer) ||
                 SDL_RenderCopy(s->renderer, s->texture, 0, 0)
             ? -1
             : (SDL_RenderPresent(s->renderer), 0);
}
static int host_close(xw_app *a) {
  struct host_state *s = a->backend_state;
  int rc = 0;
  if (!s)
    return 0;
  if (s->events && fclose(s->events))
    rc = -1;
  if (s->texture)
    SDL_DestroyTexture(s->texture);
  if (s->renderer)
    SDL_DestroyRenderer(s->renderer);
  if (s->window)
    SDL_DestroyWindow(s->window);
  if (s->initialized)
    SDL_Quit();
  free(s);
  a->backend_state = 0;
  return rc;
}
const struct xw_backend xw_host_backend = {host_open, host_next, host_present,
                                           host_close, 0};
