#ifndef HB_STORE_VIEW_H
#define HB_STORE_VIEW_H
#include "session.h"
struct hb_store_painter {
 void *context;
 void (*rect)(void *,int,int,int,int,unsigned short);
 void (*text)(void *,int,int,const char *,int,unsigned short);
};
enum hb_store_view_event {HB_STORE_VIEW_NONE,HB_STORE_VIEW_REDRAW,HB_STORE_VIEW_EXECUTE,HB_STORE_VIEW_EXIT};
/* Coordinates use the existing 240x432 front-end canvas. Input is a completed
 * tap, not a raw sample; gesture filtering belongs to the platform adapter. */
int hb_store_view_tap(struct hb_store_session *,int x,int y);
int hb_store_view_draw(const struct hb_store_session *,const char *package_name,
 const struct hb_store_painter *);
#endif
