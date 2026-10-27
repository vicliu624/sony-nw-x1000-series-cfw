#ifndef HB_QQMUSIC_DEVICES_H
#define HB_QQMUSIC_DEVICES_H
#include "qqmusic_loop.h"
#include "../../native/linux_devices.h"
struct qq_devices {
 struct hb_devices devices;unsigned short *surface;volatile int *stop;
 int opened,pressed,cancelled,x,y,close_error;
};
/* Fresh object only. Uses the existing JP framebuffer/touch adapter, not Sony
 * UI objects. No application persistence, file paths or fallback volume. */
int qq_devices_open(struct qq_devices *,struct qq_loop_io *,unsigned short *,size_t,volatile int *);
int qq_devices_close(struct qq_devices *);
struct hb_tls_time;
/* Explicit per-process QQ session interpretation. Never changes system time. */
int qq_devices_set_utc_offset(int minutes);
int qq_devices_utc_time(struct hb_tls_time *);
#endif
