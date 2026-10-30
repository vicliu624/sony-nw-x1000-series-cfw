#include "ipc.h"
#include "../../native/frontend.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/ui_font.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static uint16_t pixels[HB_DISPLAY_PIXELS];
static uint16_t scene[120*216];
static struct gm_world previous,shown;
static int interpolate;
static int show_metrics;
static unsigned receive_rate,draw_ms;
static volatile int stopped;
static uint32_t now_ms(void){struct {int32_t sec,usec;} t;extern int gm_time(void *,void *) __asm__("gettimeofday");if(gm_time(&t,0))return 0;return (uint32_t)t.sec*1000u+(uint32_t)t.usec/1000u;}
static void label(int x,int y,const char *s,uint16_t color){
 for(unsigned n=0;s[n];n++){unsigned c=(unsigned char)s[n];if(c<32||c>126)c='?';unsigned g=c-32;
  for(int row=0;row<16;row++)for(int col=0;col<16;col++){unsigned byte=hb_ui_font[g][row][col/2],a=col&1?byte&15:byte>>4;if(a>5&&x+col>=0&&x+col<240&&y+row>=0&&y+row<432)pixels[(y+row)*240+x+col]=color;}
  x+=hb_ui_advance[g];if(x>=230)break;
 }
}
static void shade(int x,int y,int w,int h){
 for(int yy=y;yy<y+h&&yy<432;yy++)for(int xx=x;xx<x+w&&xx<240;xx++){
  uint16_t p=pixels[yy*240+xx];pixels[yy*240+xx]=(uint16_t)((((p>>11)&31)*3/8<<11)|(((p>>5)&63)*3/8<<5)|((p&31)*3/8));
 }
}
static void draw(const struct gm_world *world,unsigned state,int have,uint32_t age,int quitting){
 struct gm_view v={world->layout.mw+world->layout.gap,world->layout.offset,world->layout.xw,world->layout.xh,240,432};
 shown=*world;
 if(have&&interpolate){
  float alpha=age>=50?1:(float)age/50;
  for(unsigned i=0;i<GM_COLUMNS;i++)shown.surface[i]=previous.surface[i]+(world->surface[i]-previous.surface[i])*alpha;
  shown.fish_x=previous.fish_x+(world->fish_x-previous.fish_x)*alpha;shown.fish_y=previous.fish_y+(world->fish_y-previous.fish_y)*alpha;
  float angle=world->fish_angle-previous.fish_angle,phase=world->fish_phase-previous.fish_phase;
  if(angle>3.141593f)angle-=6.283186f;
  if(angle< -3.141593f)angle+=6.283186f;
  if(phase>3.141593f)phase-=6.283186f;
  if(phase< -3.141593f)phase+=6.283186f;
  shown.fish_angle=previous.fish_angle+angle*alpha;shown.fish_phase=previous.fish_phase+phase*alpha;
 }
 (void)gm_render_fast(pixels,&v,&shown,0,scene,sizeof scene/sizeof scene[0]);
 shade(3,3,70,23);label(6,6,"< EXIT",0xffff);
 shade(158,3,79,23);
 if(show_metrics){char metrics[24];snprintf(metrics,sizeof metrics,"R%u D%u",receive_rate,draw_ms);label(163,6,metrics,0xffff);}
 else label(163,6,"Aqua a6",0xffff);
 if(!have||age>1500||quitting||state!=GM_READY){const char *s=quitting||state==GM_RESTORING?"Restoring Wi-Fi...":state==100?"Managed launcher required":state==101?"Radio worker unavailable":state==GM_REPAIR?"Recovery needs inspection":state==GM_FINISHED?"Radio stopped - exit/reopen":state==GM_STARTING?"Preparing radio...":have?"Link lost - state held":"Waiting for Mosaico...";shade(3,398,234,25);label(8,402,s,0xffff);}
}
int main(int argc,char **argv){
 struct gm_layout layout={40,40,37,66.6f,8,-13.3f};struct gm_world world;gm_init(&world,&layout,1);
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Aqua Link: Mosaico BMI270 shared two-screen water and goldfish. Managed launcher and exact user-storage radio candidate required. Tap < EXIT to restore Wi-Fi. --render-preview writes RGB565; no hardware actions.");return 0;}
 if(argc==2&&!strcmp(argv[1],"--version")){puts("0.1.0-alpha.6");return 0;}
 if(argc==2&&!strcmp(argv[1],"--render-preview")){
  for(unsigned n=0;n<180;n++)gm_step(&world,.12f,1,.01f);
  world.fish_x=65;world.fish_y=gm_surface_y(&world,65)+6;
  draw(&world,GM_READY,1,0,0);return fwrite(pixels,1,sizeof pixels,stdout)==sizeof pixels?0:74;
 }
 if(argc!=1)return 64;
 if(hb_stop_signals_install(&stopped))return 2;
 struct gm_client client={.command=-1,.events=-1};struct hb_devices devices;
 /* Acquire the foreground surface before starting radio work. */
 draw(&world,GM_STARTING,0,0,0);if(hb_devices_open(&devices,pixels,HB_DISPLAY_PIXELS,&stopped))return 2;
 int started=gm_client_start(&client),finished=started!=0,quitting=0,pressed=0,have=0,dirty=1,was_stale=1;unsigned state=started?(started==-2?100u:101u):GM_STARTING;uint32_t received=0,last_draw=0;
 uint32_t rate_window=now_ms();unsigned received_in_window=0;
 while(!stopped&&!devices.failed){
  for(unsigned i=0;i<32&&!finished;i++){struct gm_event e;int r=gm_client_event(&client,&e);if(!r)break;if(r<0){state=GM_REPAIR;dirty=1;break;}
   if(e.kind==GM_FRAME){struct gm_world next;if(!gm_decode(&next,e.packet,e.length)&&(!have||next.session!=world.session||gm_newer(next.sequence,world.sequence))){interpolate=have&&next.session==world.session;previous=interpolate?world:next;world=next;have=1;received=now_ms();dirty=1;received_in_window++;}}
   else{state=e.kind;dirty=1;if(state==GM_FINISHED)finished=1;}
  }
  if(quitting&&finished)break;
  uint32_t now=now_ms();int stale=!have||(uint32_t)(now-received)>1500;if(stale!=was_stale){dirty=1;was_stale=stale;}
  if((uint32_t)(now-rate_window)>=1000){receive_rate=(unsigned)((uint64_t)received_in_window*1000/(uint32_t)(now-rate_window));received_in_window=0;rate_window=now;if(show_metrics)dirty=1;}
  if(have&&interpolate&&(uint32_t)(now-received)<80)dirty=1;
  if(dirty&&(uint32_t)(now-last_draw)>=33){uint32_t began=now_ms();draw(&world,state,have,now-received,quitting);hb_devices_present(&devices);draw_ms=now_ms()-began;last_draw=now;dirty=0;}
  hb_devices_flush(&devices);uint8_t packet[11];int got=hb_devices_next_touch(&devices,packet,10);if(got<0)break;
  if(got>0){struct hb_touch t;hb_touch_decode(packet,&t);if(t.down){if(!pressed&&t.in_bounds&&t.y<36&&!quitting){if(t.x<75){gm_client_stop(&client);quitting=1;dirty=1;}else if(t.x>=155){show_metrics=!show_metrics;dirty=1;}}pressed=1;}else pressed=0;}
 }
 gm_client_close(&client);int failure=devices.failed||state==GM_REPAIR;if(hb_devices_close(&devices)<0)failure=1;return failure?2:0;
}
