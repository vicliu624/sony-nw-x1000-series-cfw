#include "internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unversioned"
#endif
#ifndef XW_APP_ID
#define XW_APP_ID "unconfigured"
#endif
int main(int argc, char **argv) {
  xw_app *a;
  int result;
  if (argc == 2 && !strcmp(argv[1], "--help")) {
    puts("X1000 native SDK application. --help --version --selftest do not "
         "access devices or storage.");
#ifdef XW_HOST
    puts("PC: --preview [--data existing-directory] | --render frame.ppm "
         "[--events script.txt] [--data existing-directory]");
#endif
    return 0;
  }
  if (argc == 2 && !strcmp(argv[1], "--version")) {
    puts(HB_BUILD_VERSION);
    return 0;
  }
  if (argc == 2 && !strcmp(argv[1], "--selftest")) {
    if (xw_application.api != XW_API_VERSION ||
        !xw_id_valid(xw_application.id) ||
        strcmp(xw_application.id, XW_APP_ID) || !xw_application.draw)
      return 1;
    puts("SDK metadata selftest OK (no hardware qualification)");
    return 0;
  }
  if (!xw_application.id || strcmp(xw_application.id, XW_APP_ID))
    return 64;
#ifndef XW_HOST
  if (argc != 1)
    return 64;
#endif
  a = calloc(1, sizeof(*a));
  if (!a)
    return 70;
#ifdef XW_HOST
  a->preview = 1;
  if (argc < 2) {
    free(a);
    return 64;
  }
  int i = 2;
  if (!strcmp(argv[1], "--render") && argc > 2) {
    a->render_path = argv[2];
    i = 3;
  } else if (strcmp(argv[1], "--preview")) {
    free(a);
    return 64;
  }
  for (; i < argc; i += 2) {
    if (i + 1 >= argc) {
      free(a);
      return 64;
    }
    if (!strcmp(argv[i], "--events") && a->render_path)
      a->event_path = argv[i + 1];
    else if (!strcmp(argv[i], "--data"))
      a->preview_data = argv[i + 1];
    else {
      free(a);
      return 64;
    }
  }
  result = xw_run(a, &xw_application, &xw_host_backend);
#else
  result = xw_run(a, &xw_application, &xw_native_backend);
#endif
  free(a);
  return result;
}
