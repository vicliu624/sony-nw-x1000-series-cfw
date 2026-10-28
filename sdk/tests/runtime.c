/* Public behavior through a synthetic backend. No driver/device access. */
#include "../../runtime/platform/sdk/internal.h"
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef XW_HOST
#include <sys/stat.h>
#include <unistd.h>
#endif
static int mode, opens, closes, inits, finishes, events;
static int start(xw_app *a) {
  (void)a;
  opens++;
  return mode == 1 ? -1 : 0;
}
static int next(xw_app *a, xw_event *e) {
  (void)a;
  if (mode == 3)
    return -1;
  e->type = XW_STOP;
  e->reason = mode == 6 ? XW_USB : XW_HOME;
  return 1;
}
static int present(xw_app *a) {
  (void)a;
  return mode == 4 ? -1 : 0;
}
static int end(xw_app *a) {
  (void)a;
  closes++;
  return mode == 5 ? -1 : 0;
}
static int init(xw_app *a, void *s) {
  (void)a;
  (void)s;
  inits++;
  return mode == 2 ? -1 : 0;
}
static int event(xw_app *a, void *s, const xw_event *e) {
  (void)s;
  assert(e->type == XW_STOP);
  assert(xw_is_stopping(a));
  events++;
  return 0;
}
static void draw(xw_app *a, void *s) {
  (void)s;
  xw_clear(a, xw_rgb(1, 2, 3));
}
static int finish(xw_app *a, void *s) {
  (void)a;
  (void)s;
  finishes++;
  return 0;
}
static const xw_program program = {1,    "fixture", "Fixture", 8,
                                   init, event,     draw,      finish};
static const struct xw_backend backend = {start, next, present, end};
static int busy(void *p) {
  (void)p;
  return 0;
}
#ifdef XW_HOST
static int no_temp(void *p) {
  char path[4096];
  snprintf(path, sizeof path, "%s/.sdk-write.tmp", (const char *)p);
  return access(path, F_OK) ? 1 : 0;
}
static int old_settings(void *p) {
  char path[4096];
  snprintf(path, sizeof path, "%s/settings.bin", (const char *)p);
  FILE *f = fopen(path, "rb");
  if (!f)
    return 0;
  int first = fgetc(f);
  fclose(f);
  return first == 1;
}
#endif
int main(int argc, char **argv) {
  xw_app *a = calloc(1, sizeof(*a));
  assert(a);
  for (mode = 0; mode <= 6; mode++) {
    memset(a, 0, sizeof(*a));
    opens = closes = inits = finishes = events = 0;
    int rc = xw_run(a, &program, &backend);
    assert((rc == 0) == (mode == 0 || mode == 6));
    assert(opens == 1 && closes == 1);
    assert(inits == (mode != 1));
    assert(finishes == (mode != 1));
    assert(events == ((mode == 0 || mode == 5 || mode == 6) ? 1 : 0));
  }
  memset(a, 0, sizeof(*a));
  a->program = &program;
  a->preview = 1;
  xw_reset_clip(a);
  xw_clear(a, 0);
  xw_clip(a, (xw_rect){5, 5, 2, 2});
  xw_fill(a, (xw_rect){INT_MIN, INT_MIN, INT_MAX, INT_MAX}, 0xffff);
  assert(a->pixels[5 * 240 + 5] == 0);
  xw_fill(a, (xw_rect){0, 0, 240, 432}, 0xffff);
  assert(a->pixels[5 * 240 + 5] == 0xffff && a->pixels[4 * 240 + 5] == 0);
  assert(xw_text(a, INT_MAX, INT_MIN, "hello", 4, 0xffff) < 0);
  assert(xw_text(a, 0, 0, "\xc3\xa9", 1, 0xffff) < 0);
  uint16_t image[4] = {1, 2, 3, 4};
  assert(xw_image(a, 0, 0, 3, 3, image, 4, 0, 0) < 0);
  xw_reset_clip(a);
  assert(!xw_image(a, 0, 0, 2, 2, image, 4, 1, 1));
  assert(a->pixels[0] == 0 && a->pixels[1] == 2);
  xw_button button = {0};
  xw_rect rect = {10, 10, 30, 30};
  xw_event e = {XW_TOUCH_DOWN, 20, 20, 0, 0};
  assert(!xw_button_event(&button, rect, &e));
  e.type = XW_TOUCH_UP;
  assert(xw_button_event(&button, rect, &e));
  e.type = XW_TOUCH_DOWN;
  xw_button_event(&button, rect, &e);
  e.type = XW_TOUCH_MOVE;
  e.x = 39;
  xw_button_event(&button, rect, &e);
  e.type = XW_TOUCH_UP;
  e.x = 20;
  assert(!xw_button_event(&button, rect, &e));
  unsigned char value[4] = {1, 2, 3, 4};
  assert(xw_data_write(a, "../escape", value, 4) == XW_STORAGE_INVALID);
#ifdef XW_HOST
  unsigned char out[5];
  size_t used = 9;
  assert(argc == 2);
  a->preview_data = argv[1];
  assert(xw_data_read(a, "settings.bin", out, 4, &used) == XW_STORAGE_MISSING &&
         used == 0);
  assert(!xw_data_write(a, "settings.bin", value, 4));
  assert(!xw_data_read(a, "settings.bin", out, 4, &used) && used == 4 &&
         !memcmp(out, value, 4));
  assert(!xw_storage_set_owner(a, busy, 0));
  assert(xw_data_write(a, "settings.bin", out, 3) == XW_STORAGE_OWNERSHIP);
  assert(!xw_storage_set_owner(a, 0, 0));
  char path[4096];
  snprintf(path, sizeof path, "%s/link.bin", argv[1]);
  assert(!symlink("settings.bin", path));
  assert(xw_data_read(a, "link.bin", out, 4, &used) == XW_STORAGE_BOUNDARY);
  assert(xw_data_write(a, "link.bin", out, 3) == XW_STORAGE_BOUNDARY);
  snprintf(path, sizeof path, "%s/.sdk-write.tmp", argv[1]);
  FILE *f = fopen(path, "wb");
  assert(f);
  assert(!fclose(f));
  assert(xw_data_write(a, "settings.bin", out, 3) == XW_STORAGE_BOUNDARY);
  assert(!xw_data_read(a, "settings.bin", out, 4, &used) && used == 4);
  assert(!unlink(path));
  assert(!xw_storage_set_owner(a, no_temp, argv[1]));
  assert(xw_data_write(a, "settings.bin", value, 4) == XW_STORAGE_OWNERSHIP);
  assert(!xw_storage_set_owner(a, 0, 0));
  assert(!xw_data_read(a, "settings.bin", out, 4, &used) && out[0] == 1);
  assert(!unlink(path)); /* explicit fixture cleanup, under host ownership */
  assert(!xw_storage_set_owner(a, old_settings, argv[1]));
  value[0] = 9;
  assert(xw_data_write(a, "settings.bin", value, 4) == XW_STORAGE_UNCERTAIN);
  assert(!xw_storage_set_owner(a, 0, 0));
  assert(!xw_data_read(a, "settings.bin", out, 4, &used) && out[0] == 9);
  char original[4096];
  snprintf(original, sizeof original, "%s/settings.bin", argv[1]);
  snprintf(path, sizeof path, "%s/hard.bin", argv[1]);
  assert(!link(original, path));
  assert(xw_data_read(a, "hard.bin", out, 4, &used) == XW_STORAGE_BOUNDARY);
  assert(!unlink(path));
  snprintf(path, sizeof path, "%s/pipe.bin", argv[1]);
  if (!mkfifo(path, 0600))
    assert(xw_data_read(a, "pipe.bin", out, 4, &used) == XW_STORAGE_BOUNDARY);
  else {
    assert(errno == EPERM || errno == EOPNOTSUPP || errno == ENOSYS);
    puts("SKIP FIFO: fixture filesystem does not support named pipes");
  }
#else
  (void)argc;
  (void)argv;
  (void)busy;
  assert(xw_data_write(a, "settings.bin", value, 4) == XW_STORAGE_OWNERSHIP);
#endif
  xw_request_exit(a);
  assert(xw_data_write(a, "settings.bin", value, 4) == XW_STORAGE_STOPPED);
  free(a);
  puts("SDK lifecycle, cleanup, canvas, touch and storage contracts passed");
  return 0;
}
