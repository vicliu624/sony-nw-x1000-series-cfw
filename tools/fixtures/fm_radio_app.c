#include <assert.h>
#include <stdio.h>
#include "../../runtime/native/linux_devices.h"
int hb_fm_demo(void);
const unsigned short *hb_fm_preview(int);
static int event,closed,frames,mode;static volatile int *stop;
int hb_stop_signals_install(volatile int *p){stop=p;return 0;}
int hb_devices_open(struct hb_devices *d,const unsigned short *p,unsigned n,volatile int *s){assert(n==HB_DISPLAY_PIXELS&&p[0]);*d=(struct hb_devices){0};d->stop=s;d->surface=p;return mode==1?-1:0;}
int hb_devices_close(struct hb_devices *d){(void)d;closed++;return mode==4?-1:0;}
void hb_devices_present(struct hb_devices *d){frames++;if(mode==0&&frames==1){FILE *f=fopen("work/fm-radio-review/main.rgb565","wb");assert(f);assert(fwrite(d->surface,2,HB_DISPLAY_PIXELS,f)==HB_DISPLAY_PIXELS);assert(!fclose(f));}}
void hb_devices_flush(struct hb_devices *d){if(mode==2)*stop=1;if(mode==3)d->failed=1;}
int hb_devices_next_touch(struct hb_devices *d,unsigned char p[11],int timeout){(void)d;assert(timeout==50);if(*stop||mode==3)return -1;assert(event<4);unsigned x=80,y=event<2?180:400;unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;for(int i=0;i<11;i++)p[i]=0;p[1]=event%2==0;p[2]=rx>>8;p[3]=rx;p[4]=ry>>8;p[5]=ry;event++;return 1;}
int main(void){
 const char *names[]={"tuning","favorites","results","keypad","pressed","error"};
 for(int page=0;page<6;page++){char path[96];snprintf(path,sizeof(path),"work/fm-radio-review/%s.rgb565",names[page]);FILE *f=fopen(path,"wb");assert(f);assert(fwrite(hb_fm_preview(page),2,HB_DISPLAY_PIXELS,f)==HB_DISPLAY_PIXELS);assert(!fclose(f));}
for(mode=0;mode<5;mode++){event=closed=frames=0;int result=hb_fm_demo();assert(result==((mode==1||mode==3||mode==4)?2:0));assert(closed==(mode!=1));if(!mode)assert(event==4&&frames==4);}return 0;}
