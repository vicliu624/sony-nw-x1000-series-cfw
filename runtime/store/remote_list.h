#ifndef HB_STORE_REMOTE_LIST_H
#define HB_STORE_REMOTE_LIST_H
#include "remote_catalog.h"
#include "ui_loop.h"
enum hb_remote_list_action {HB_REMOTE_NONE,HB_REMOTE_REDRAW,HB_REMOTE_SELECT,HB_REMOTE_EXIT};
struct hb_remote_list {unsigned count,page,map[HB_REMOTE_CATALOG_ENTRIES];int selected;};
/* Catalog remains immutable/alive. Running app ID is excluded, not updated in
 * place while executing. Selection returns original catalog index. */
int hb_remote_list_init(struct hb_remote_list *,const struct hb_remote_catalog *,const char *running_id);
int hb_remote_list_tap(struct hb_remote_list *,int x,int y);
int hb_remote_list_draw(const struct hb_remote_list *,const struct hb_remote_catalog *,const struct hb_store_painter *);
int hb_remote_list_run(const struct hb_remote_catalog *,const char *running_id,const struct hb_store_painter *,const struct hb_store_ui_io *);
#endif
