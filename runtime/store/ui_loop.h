#ifndef HB_STORE_UI_LOOP_H
#define HB_STORE_UI_LOOP_H
#include "view.h"
struct hb_store_ui_io {
 void *context;
 /* 1=11-byte touch sample, 0=idle, -1=normal stop, -2=error.
  * Platform owns polling, original lifecycle events and hardware resources. */
 int (*next)(void *,unsigned char packet[11]);
 int (*present)(void *);
};
/* Uses the original front-end coordinate decoder. Does not acquire devices.
 * Synchronous installer means next() is not polled while execute() runs. */
int hb_store_ui_run(struct hb_store_session *,const char *name,
 const struct hb_store_painter *,const struct hb_store_ui_io *);
#endif
