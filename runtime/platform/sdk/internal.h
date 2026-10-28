#ifndef XW_INTERNAL_H
#define XW_INTERNAL_H
#include <x1000/app.h>
#include <x1000/storage.h>
struct xw_backend {
  int (*open)(xw_app *);
  int (*next)(xw_app *, xw_event *);
  int (*present)(xw_app *);
  int (*close)(xw_app *);
  int (*stopping)(const xw_app *);
};
struct xw_app {
  uint16_t pixels[XW_WIDTH * XW_HEIGHT];
  xw_rect clip;
  const xw_program *program;
  volatile int stop;
  int dirty, preview, reason, failed, pressed;
  int (*poll_stop)(const xw_app *);
  xw_storage_owner owner;
  void *owner_context, *backend_state;
  /* Host-only paths are never accepted by a device executable. */
  const char *preview_data, *render_path, *event_path, *resource_root;
};
int xw_run(xw_app *, const xw_program *, const struct xw_backend *);
int xw_id_valid(const char *);
int xw_filename_valid(const char *);
int xw_storage_access(xw_app *);
extern const struct xw_backend xw_native_backend;
#ifdef XW_HOST
extern const struct xw_backend xw_host_backend;
#endif
#endif
