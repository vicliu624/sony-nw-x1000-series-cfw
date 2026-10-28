/* External C app example. No Sony function addresses, hooks, or filesystem writes. */
#include <stdio.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/display.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include "../../../sdk/include/x1000/services/touch.h"
#include "../../../sdk/include/x1000/services/font5x7.h"
static unsigned short canvas[HB_DISPLAY_PIXELS];
static volatile int stop;
static void box(int x,int y,int w,int h,unsigned short color) {
 for(int j=y;j<y+h&&j<432;j++)for(int i=x;i<x+w&&i<240;i++)canvas[j*240+i]=color;
}
static void text(int x,int y,const char *s) {
 for(;*s&&x<228;s++,x+=12) {
  int g=*s>='A'&&*s<='Z'?*s-'A'+10:-1;
  if(g<0)continue;
  for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(glyph[g][j]&(1<<(4-i)))box(x+i*2,y+j*2,2,2,0xffff);
 }
}
static void draw(unsigned color) {
 static const unsigned short colors[]={0x001f,0x0320,0x580c};
 box(0,0,240,432,colors[color%3]);text(12,18,"NATIVE C APP");
 text(12,140,"TAP TO CHANGE");text(12,164,"THE COLOUR");
 box(0,384,240,48,0x18c3);text(18,402,"BACK TO APPS");
}
int hb_graphics_demo(void) {
 struct hb_devices devices;unsigned color=0;int pressed=0,cancel=0,x=0,y=0;
 stop=0;
 if(hb_stop_signals_install(&stop))return 2;
 draw(color);
 if(hb_devices_open(&devices,canvas,HB_DISPLAY_PIXELS,&stop))return stop?0:2;
 hb_devices_present(&devices);
 while(!stop&&!devices.failed) {
  hb_devices_flush(&devices);
  unsigned char packet[11];int got=hb_devices_next_touch(&devices,packet,50);
  if(got<0)break;
  if(!got)continue;
  struct hb_touch touch;hb_touch_decode(packet,&touch);
  if(touch.down){if(!pressed){x=touch.x;y=touch.y;cancel=0;}pressed=1;
   if(!touch.in_bounds||(int)touch.x-x>12||x-(int)touch.x>12||(int)touch.y-y>12||y-(int)touch.y>12)cancel=1;
   continue;}
  if(!pressed)continue;
  pressed=0;
  if(cancel||!touch.in_bounds)continue;
  if(y>=384)break;
  draw(++color);hb_devices_present(&devices);
 }
 int failed=devices.failed;
 if(hb_devices_close(&devices)<0)return 2;
 return stop?0:failed?2:0;
}
#ifndef HB_DEMO_TEST
int main(int argc,char **argv) {
 if(argc==1)return hb_graphics_demo();
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Native C graphics example. Tap to change colour; BACK TO APPS exits. No storage writes.");return 0;}
 return 64;
}
#endif
