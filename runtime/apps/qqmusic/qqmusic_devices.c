#include "qqmusic_devices.h"
#include "../../native/frontend.h"
#include "../../store/deadline.h"
#include "../../store/tls_platform.h"
#include <poll.h>
#include <string.h>
static int utc_offset_minutes;
int qq_devices_set_utc_offset(int minutes){if(minutes< -720||minutes>840||minutes%15)return -1;utc_offset_minutes=minutes;return 0;}
int qq_devices_utc_time(struct hb_tls_time *out){
 struct hb_tls_time value;int rc;int64_t adjusted;
 if(!out)return HB_TLS_PLATFORM_TIME;
 rc=hb_tls_current_time(&value);if(rc)return rc;
 if(utc_offset_minutes){
  adjusted=(int64_t)value.unix_seconds-(int64_t)utc_offset_minutes*60;
  if(adjusted<0||adjusted>2147483647)return HB_TLS_PLATFORM_TIME;
  value.unix_seconds=(uint64_t)adjusted;value.days=719528u+(unsigned)(value.unix_seconds/86400u);value.seconds=(unsigned)(value.unix_seconds%86400u);
 }
 *out=value;return 0;
}
int qq_devices_close(struct qq_devices *d) {
 if(!d)return -1;
 if(d->opened){if(hb_devices_close(&d->devices))d->close_error=1;d->opened=0;}
 d->pressed=d->cancelled=0;return d->close_error?-1:0;
}
static int clock_read(void *context,uint64_t *now,uint64_t *unix_ms) {
 struct qq_devices *d=context;unsigned long long monotonic;struct hb_tls_time time;
 if(!d->opened||!now||!unix_ms||hb_monotonic_millis(&monotonic)||qq_devices_utc_time(&time))return -1;
 *now=monotonic;*unix_ms=time.unix_seconds*1000u;return 0;
}
static int present(void *context,const unsigned short *pixels,size_t count) {
 struct qq_devices *d=context;
 if(!d->opened||pixels!=d->surface||count!=QQ_UI_PIXELS||d->devices.failed)return -1;
 hb_devices_present(&d->devices);return d->devices.failed?-1:0;
}
static int touch(void *context,int *x,int *y) {
 struct qq_devices *d=context;unsigned char packet[11];struct hb_touch value;int got,valid;
 if(!d->opened||!x||!y)return -2;
 if(*d->stop)return -1;
 hb_devices_flush(&d->devices);if(d->devices.failed)return -2;
 got=hb_devices_next_touch(&d->devices,packet,0);if(got<=0)return got;
 hb_touch_decode(packet,&value);
 /* Decoder preserves Sony's saturated Y rule; app hits reject raw overflow. */
 valid=value.in_bounds&&value.raw_x<2929u&&value.raw_y<5281u;
 if(value.down) {
  if(!d->pressed){d->x=(int)value.x;d->y=(int)value.y;d->cancelled=!valid;d->pressed=1;*x=d->x;*y=d->y;return valid?2:3;}
  d->pressed=1;
  if(!d->cancelled&&(!valid||(int)value.x-d->x>12||d->x-(int)value.x>12||(int)value.y-d->y>12||d->y-(int)value.y>12)){d->cancelled=1;return 3;}
  return 0;
 }
 if(!d->pressed)return 0;
 d->pressed=0;
 if(d->cancelled||!valid)return 3;
 *x=d->x;*y=d->y;return 1;
}
static void idle(void *context,unsigned maximum_ms) {
 struct qq_devices *d=context;
 if(!d->opened||*d->stop||d->devices.failed)return;
 if(maximum_ms>20)maximum_ms=20;
 poll(0,0,(int)maximum_ms);hb_devices_flush(&d->devices);
}
static int close_io(void *context){return qq_devices_close(context);}
int qq_devices_open(struct qq_devices *d,struct qq_loop_io *io,unsigned short *surface,size_t count,volatile int *stop) {
 if(!d||!io)return -1;
 memset(d,0,sizeof(*d));memset(io,0,sizeof(*io));
 if(!surface||count!=QQ_UI_PIXELS||!stop||*stop)return -1;
 d->surface=surface;d->stop=stop;
 if(hb_devices_open(&d->devices,surface,(unsigned)count,stop)){d->close_error=d->devices.release_failed;return -1;}
 d->opened=1;io->context=d;io->clock=clock_read;io->touch=touch;io->present=present;io->idle=idle;io->close=close_io;return 0;
}
