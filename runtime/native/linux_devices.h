#ifndef HB_LINUX_DEVICES_H
#define HB_LINUX_DEVICES_H
#define HB_DISPLAY_PIXELS (240u * 432u)
/* Framebuffer/touch state owned by one external program, not Sony UI objects. */
struct hb_devices {
    int fb, touch;
    unsigned short *pixels;
    unsigned length;
    int pending, failed, release_failed;
    const unsigned short *surface;
    volatile int *stop;
};
int hb_devices_open(struct hb_devices *, const unsigned short *surface,
                    unsigned pixel_count, volatile int *stop_requested);
int hb_devices_close(struct hb_devices *);
void hb_devices_present(struct hb_devices *);
void hb_devices_flush(struct hb_devices *);
/* 1: packet, 0: no packet, -1: stop, -2: device failure. */
int hb_devices_next_touch(struct hb_devices *, unsigned char packet[11], int timeout_ms);
#endif
