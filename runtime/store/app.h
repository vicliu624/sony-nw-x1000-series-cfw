#ifndef HB_STORE_APP_H
#define HB_STORE_APP_H
#include "browser.h"
struct hb_store_platform {
 void *context;
 /* Platform supplies original device acquisition/presentation/input. On
  * failure it may have partial resources: close is still called exactly once.
  * close must finish release before returning, including pending display work. */
 int (*open)(void *,unsigned short *pixels,unsigned count,volatile int *stop,struct hb_store_ui_io *);
 int (*close)(void *);
};
/* Owns store allocations and SIGTERM scope. No updater, device implementation
 * or network transport here. Platform/context and paths remain caller-owned. */
int hb_store_app_run(const char *apps_root,const char *package_root,
 unsigned long long reserve,const struct hb_store_platform *);
#endif
