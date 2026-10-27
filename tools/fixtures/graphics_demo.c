#include <assert.h>
#include "../../runtime/native/linux_devices.h"
int hb_graphics_demo(void);
static int event,closed,frames,mode;static volatile int *stop;
int hb_stop_signals_install(volatile int *p){stop=p;return 0;}
int hb_devices_open(struct hb_devices *d,const unsigned short *p,unsigned n,volatile int *s){assert(n==HB_DISPLAY_PIXELS&&p[0]);*d=(struct hb_devices){0};d->stop=s;return mode==1?-1:0;}
int hb_devices_close(struct hb_devices *d){(void)d;closed++;return mode==4?-1:0;}
void hb_devices_present(struct hb_devices *d){(void)d;frames++;}
void hb_devices_flush(struct hb_devices *d){if(mode==2)*stop=1;if(mode==3)d->failed=1;}
int hb_devices_next_touch(struct hb_devices *d,unsigned char p[11],int timeout){(void)d;assert(timeout==50);if(*stop||mode==3)return -1;assert(event<4);unsigned x=80,y=event<2?100:400;unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;for(int i=0;i<11;i++)p[i]=0;p[1]=event%2==0;p[2]=rx>>8;p[3]=rx;p[4]=ry>>8;p[5]=ry;event++;return 1;}
int main(void){for(mode=0;mode<5;mode++){event=closed=frames=0;int result=hb_graphics_demo();assert(result==((mode==1||mode==3||mode==4)?2:0));assert(closed==(mode!=1));if(!mode)assert(event==4&&frames==2);}return 0;}
