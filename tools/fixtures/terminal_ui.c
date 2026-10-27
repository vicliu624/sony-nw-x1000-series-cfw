/* Actual graphical app with synthetic display/touch; no player access. */
#include "../../runtime/native/linux_devices.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned short const *surface;
static int events;
int hb_devices_open(struct hb_devices *d,const unsigned short *p,unsigned count,volatile int *stop){
 (void)stop;if(count!=HB_DISPLAY_PIXELS)return -1;memset(d,0,sizeof *d);surface=p;return 0;
}
void hb_devices_present(struct hb_devices *d){
 (void)d;FILE *f=fopen("work/terminal-review/screen.rgb565","wb");if(!f)abort();if(fwrite(surface,2,HB_DISPLAY_PIXELS,f)!=HB_DISPLAY_PIXELS)abort();if(fclose(f))abort();
}
void hb_devices_flush(struct hb_devices *d){(void)d;}
int hb_devices_next_touch(struct hb_devices *d,unsigned char p[11],int timeout){
 (void)d;(void)timeout;memset(p,0,11);p[1]=events++==0?1:0;p[2]=5;p[3]=184;p[4]=1;p[5]=44;return 1;
}
int hb_devices_close(struct hb_devices *d){(void)d;return 0;}
