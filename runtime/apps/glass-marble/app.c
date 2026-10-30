#include "ipc.h"
#include "../../native/frontend.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/ui_font.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static uint16_t pixels[HB_DISPLAY_PIXELS];
static volatile int stopped;
static uint32_t now_ms(void){struct {int32_t sec,usec;} t;extern int gm_time(void *,void *) __asm__("gettimeofday");if(gm_time(&t,0))return 0;return (uint32_t)t.sec*1000u+(uint32_t)t.usec/1000u;}
static void label(int x,int y,const char *s,uint16_t color){
 for(unsigned n=0;s[n];n++){unsigned c=(unsigned char)s[n];if(c<32||c>126)c='?';unsigned g=c-32;
  for(int row=0;row<16;row++)for(int col=0;col<16;col++){unsigned byte=hb_ui_font[g][row][col/2],a=col&1?byte&15:byte>>4;if(a>5&&x+col>=0&&x+col<240&&y+row>=0&&y+row<432)pixels[(y+row)*240+x+col]=color;}
  x+=hb_ui_advance[g];if(x>=230)break;
 }
}
static void draw(const struct gm_world *world,unsigned state,int have,uint32_t age,int quitting){
 struct gm_view v={world->layout.mw+world->layout.gap,world->layout.offset,world->layout.xw,world->layout.xh,240,432};
 gm_render(pixels,&v,world,have&&age<250?(float)age/1000:0);
 label(6,6,"< EXIT",0xc618);
 if(!have||age>500||quitting){const char *s=quitting?"Restoring Wi-Fi...":state==GM_REPAIR?"Recovery needs inspection":state==GM_STARTING?"Preparing radio...":have?"Link lost - state held":"Waiting for Mosaico...";label(8,402,s,0xffff);}
}
int main(int argc,char **argv){
 struct gm_layout layout={40,40,37,66.6f,8,-13.3f};struct gm_world world;gm_init(&world,&layout,1);
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Glass Marble: Mosaico BMI270 shared two-screen marble tray. Managed launcher and exact user-storage radio candidate required. Tap < EXIT to restore Wi-Fi. --render-preview writes RGB565; no hardware actions.");return 0;}
 if(argc==2&&!strcmp(argv[1],"--version")){puts("0.1.0-alpha.1");return 0;}
 if(argc==2&&!strcmp(argv[1],"--render-preview")){
  for(unsigned i=0;i<GM_COUNT;i++){world.ball[i].x=layout.mw+layout.gap+5+(i%4)*8.5f;world.ball[i].y=layout.offset+7+(i/4)*12.5f;}
  draw(&world,GM_READY,1,0,0);return fwrite(pixels,1,sizeof pixels,stdout)==sizeof pixels?0:74;
 }
 if(argc!=1)return 64;
 if(hb_stop_signals_install(&stopped))return 2;
 struct gm_client client={.command=-1,.events=-1};struct hb_devices devices;
 /* Acquire the foreground surface before starting radio work. */
 draw(&world,GM_STARTING,0,0,0);if(hb_devices_open(&devices,pixels,HB_DISPLAY_PIXELS,&stopped))return 2;
 int started=gm_client_start(&client),finished=started!=0,quitting=0,pressed=0,have=0;unsigned state=started?GM_REPAIR:GM_STARTING;uint32_t received=0,last_draw=0;
 while(!stopped&&!devices.failed){
  for(unsigned i=0;i<32&&!finished;i++){struct gm_event e;int r=gm_client_event(&client,&e);if(!r)break;if(r<0){state=GM_REPAIR;break;}
   if(e.kind==GM_FRAME){struct gm_world next;if(!gm_decode(&next,e.packet,e.length)&&(!have||next.session!=world.session||gm_newer(next.sequence,world.sequence))){world=next;have=1;received=now_ms();}}
   else{state=e.kind;if(state==GM_FINISHED)finished=1;}
  }
  if(quitting&&finished)break;
  uint32_t now=now_ms();if((uint32_t)(now-last_draw)>=33){draw(&world,state,have,now-received,quitting);hb_devices_present(&devices);last_draw=now;}
  hb_devices_flush(&devices);uint8_t packet[11];int got=hb_devices_next_touch(&devices,packet,10);if(got<0)break;
  if(got>0){struct hb_touch t;hb_touch_decode(packet,&t);if(t.down){if(!pressed&&t.in_bounds&&t.x<75&&t.y<36&&!quitting){gm_client_stop(&client);quitting=1;}pressed=1;}else pressed=0;}
 }
 gm_client_close(&client);int failure=devices.failed||state==GM_REPAIR;if(hb_devices_close(&devices)<0)failure=1;return failure?2:0;
}
