#ifndef X1000_SDK_APP_H
#define X1000_SDK_APP_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define XW_API_VERSION 1
#define XW_WIDTH 240
#define XW_HEIGHT 432
typedef struct xw_app xw_app;
typedef struct {
  int x, y, width, height;
} xw_rect;
enum xw_event_type {
  XW_TICK,
  XW_TOUCH_DOWN,
  XW_TOUCH_MOVE,
  XW_TOUCH_UP,
  XW_STOP
};
enum xw_stop_reason {
  XW_EXIT_REQUESTED,
  XW_HOME,
  XW_SIGNAL,
  XW_USB,
  XW_DEVICE_ERROR
};
typedef struct {
  enum xw_event_type type;
  int x, y;
  unsigned elapsed_ms;
  enum xw_stop_reason reason;
} xw_event;
/* One foreground app per process. finish runs after init, including init
 * failure. Nonzero callback results are errors. Event/draw callbacks must
 * remain bounded. */
typedef struct {
  unsigned api;
  const char *id, *title;
  size_t state_bytes;
  int (*init)(xw_app *, void *state);
  int (*event)(xw_app *, void *state, const xw_event *);
  void (*draw)(xw_app *, void *state);
  int (*finish)(xw_app *, void *state);
} xw_program;
/* Define this in the app. SDK entry handles safe CLI and the native/host loop.
 */
extern const xw_program xw_application;
void xw_request_exit(xw_app *);
void xw_redraw(xw_app *);
int xw_is_stopping(const xw_app *);
int xw_is_preview(const xw_app *);
uint16_t xw_rgb(unsigned r, unsigned g, unsigned b);
void xw_clear(xw_app *, uint16_t color);
void xw_clip(xw_app *, xw_rect);
void xw_reset_clip(xw_app *);
void xw_fill(xw_app *, xw_rect, uint16_t color);
/* Printable ASCII, proportional 16px Noto raster, scales 1..4. No UTF-8. */
int xw_text(xw_app *, int x, int y, const char *, unsigned scale,
            uint16_t color);
int xw_image(xw_app *, int x, int y, unsigned width, unsigned height,
             const uint16_t *pixels, size_t count, int transparent,
             uint16_t key);
typedef struct {
  int armed, x, y, cancelled;
} xw_button;
/* Activate on release inside the original button; cancel after a drag >12px. */
int xw_button_event(xw_button *, xw_rect, const xw_event *);
void xw_button_draw(xw_app *, xw_rect, const char *label, int pressed);
const char *xw_sdk_version(void);
#ifdef __cplusplus
}
#endif
#endif
