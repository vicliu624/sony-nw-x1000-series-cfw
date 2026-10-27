#ifndef HB_APP_CATALOG_H
#define HB_APP_CATALOG_H
#include "frontend.h"
struct hb_app {char id[33],name[49],version[33],folder[256],sha[65];unsigned bytes;};
struct hb_catalog {struct hb_app apps[HB_MAX_APPS];unsigned count,rejected;};
/* Scan preserves a usable partial list on read failure. Store remains first. */
int hb_catalog_scan(struct hb_catalog *, const char *root, volatile int *stop);
/* Recheck executable bytes immediately before launch. */
int hb_catalog_verify(const struct hb_app *, volatile int *stop);
int hb_app_executable(const struct hb_app *, char path[256]);
#endif
