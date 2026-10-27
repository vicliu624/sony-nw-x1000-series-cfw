#ifndef HB_STORE_CATALOG_VIEW_H
#define HB_STORE_CATALOG_VIEW_H
#include "catalog_posix.h"
#include "view.h"
struct hb_store_catalog_view {unsigned page;int selected;};
enum hb_store_catalog_event {HB_CATALOG_NONE,HB_CATALOG_REDRAW,HB_CATALOG_SELECT,HB_CATALOG_EXIT};
void hb_store_catalog_view_init(struct hb_store_catalog_view *);
int hb_store_catalog_tap(struct hb_store_catalog_view *,const struct hb_store_catalog *,int x,int y);
int hb_store_catalog_draw(const struct hb_store_catalog_view *,const struct hb_store_catalog *,const struct hb_store_painter *);
#endif
