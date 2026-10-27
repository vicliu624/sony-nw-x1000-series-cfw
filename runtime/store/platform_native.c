#define _DEFAULT_SOURCE 1
#include "platform_native.h"
#include "../native/linux_devices.h"
#include <errno.h>
#include <unistd.h>

struct native_context { struct hb_devices devices; int active; };
static struct native_context context;

static int wait_display_tick(void) {
    int result=usleep(10000);
    return result<0&&errno!=EINTR?-1:0;
}
static int store_present(void *opaque) {
    struct native_context *c=opaque;
    if(!c->active||*c->devices.stop)return -1;
    hb_devices_present(&c->devices);
    for(unsigned attempt=0;c->devices.pending&&!c->devices.failed&&
        !*c->devices.stop&&attempt<200;attempt++) {
        if(wait_display_tick())return -1;
        hb_devices_flush(&c->devices);
    }
    return c->devices.pending||c->devices.failed||*c->devices.stop?-1:0;
}
static int store_next(void *opaque,unsigned char packet[11]) {
    struct native_context *c=opaque;
    if(!c->active)return -2;
    if(*c->devices.stop)return -1;
    hb_devices_flush(&c->devices);
    if(c->devices.failed)return -2;
    int result=hb_devices_next_touch(&c->devices,packet,50);
    return *c->devices.stop?-1:result;
}
static int store_open(void *opaque,unsigned short *pixels,unsigned count,
                      volatile int *stop,struct hb_store_ui_io *io) {
    struct native_context *c=opaque;
    if(c->active||!pixels||count!=HB_DISPLAY_PIXELS||!stop||!io)return -1;
    c->active=1;
    if(hb_devices_open(&c->devices,pixels,count,stop))return -1;
    io->context=c;io->next=store_next;io->present=store_present;
    return 0;
}
static int store_close(void *opaque) {
    struct native_context *c=opaque;
    if(!c->active)return 0;
    int result=hb_devices_close(&c->devices);
    c->active=0;
    return result;
}
int hb_store_native_platform(struct hb_store_platform *platform) {
    if(!platform||context.active)return -1;
    platform->context=&context;platform->open=store_open;platform->close=store_close;
    return 0;
}
