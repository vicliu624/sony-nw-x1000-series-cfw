#ifndef HB_STORE_CATALOG_LOOP_H
#define HB_STORE_CATALOG_LOOP_H
#include "catalog_view.h"
#include "ui_loop.h"
/* Returns selected index, -1 on Back/platform normal stop, -2 on error.
 * Does not scan, install, own devices or modify the catalog. */
int hb_store_catalog_run(const struct hb_store_catalog *,const struct hb_store_painter *,const struct hb_store_ui_io *);
#endif
