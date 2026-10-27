#ifndef HB_STORE_CANVAS_H
#define HB_STORE_CANVAS_H
#include "view.h"
struct hb_store_canvas { unsigned short *pixels;unsigned count; };
/* Caller-owned, tightly packed 240x432 RGB565 surface; no device operations. */
int hb_store_canvas_init(struct hb_store_canvas *,unsigned short *,unsigned count,
 struct hb_store_painter *);
#endif
