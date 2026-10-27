#ifndef HB_STORE_BROWSER_H
#define HB_STORE_BROWSER_H
#include "catalog_loop.h"
#include "session_local.h"
/* Caller-owned (~85KiB) workspace; keep its address stable throughout run. */
struct hb_store_browser {
 struct hb_store_catalog catalog;
 struct hb_bundle bundle;
 struct hb_store_local_session selected;
};
/* Local directory browser only, no downloads or device acquisition. Rescans
 * after returning from a selected package. 0=Back/platform stop, -1=error. */
int hb_store_browser_run(const char *apps_root,const char *package_root,
 unsigned long long reserve,struct hb_store_browser *,const struct hb_store_painter *,
 const struct hb_store_ui_io *,volatile int *stop);
/* Owning app can omit its own ID until an exit-first self-update exists. */
int hb_store_browser_run_for_app(const char *apps_root,const char *package_root,
 unsigned long long reserve,struct hb_store_browser *,const struct hb_store_painter *,
 const struct hb_store_ui_io *,volatile int *stop,const char *running_id);
#endif
