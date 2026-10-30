#include "../../runtime/apps/glass-marble/marble.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static struct gm_layout layout={40,40,37,66.6f,8,-13.3f};
int main(int argc,char **argv){
 struct gm_world w,decoded;uint8_t packet[GM_PACKET];gm_init(&w,&layout,123);
 if(argc==2&&!strcmp(argv[1],"--movie")){
  static uint16_t m[240*240],x[120*216];struct gm_view mv={0,0,40,40,240,240},xv={48,-13.3f,37,66.6f,120,216};
  for(unsigned frame=0;frame<120;frame++){
   for(unsigned tick=0;tick<6;tick++)gm_step(&w,.35f*sinf(frame*6.2831853f/120),1,.01f);
   gm_render(m,&mv,&w,0);gm_render(x,&xv,&w,0);
   if(fwrite(m,2,240*240,stdout)!=240*240||fwrite(x,2,120*216,stdout)!=120*216)return 1;
  }return 0;
 }
 if(argc==2){
  for(unsigned n=0;n<180;n++)gm_step(&w,.12f,1,.01f);
  w.fish_x=62;w.fish_y=gm_surface_y(&w,62)+6;
  static uint16_t m[480*480],x[240*432];struct gm_view mv={0,0,40,40,480,480},xv={48,-13.3f,37,66.6f,240,432};gm_render(m,&mv,&w,0);gm_render(x,&xv,&w,0);
  if(fwrite(m,2,480*480,stdout)!=480*480||fwrite(x,2,240*432,stdout)!=240*432)return 1;
  return 0;
 }
 assert(GM_PACKET==120);assert(gm_encode(&w,packet,sizeof packet)==GM_PACKET);assert(!gm_decode(&decoded,packet,sizeof packet));assert(decoded.session==123);
 struct gm_world saved=decoded;packet[57]^=1;assert(gm_decode(&decoded,packet,sizeof packet));assert(!memcmp(&saved,&decoded,sizeof saved));packet[57]^=1;
 assert(gm_decode(&decoded,packet,sizeof packet-1));assert(gm_newer(0,0xffffffffu));assert(!gm_newer(7,7));assert(!gm_newer(6,7));
 float volume=w.volume;
 for(unsigned t=0;t<400;t++){
  gm_step(&w,.4f,1,.01f);
  assert(fabsf(gm_water_volume(&w)-volume)<1.0f);
  assert(isfinite(w.fish_x)&&isfinite(w.fish_y)&&isfinite(w.fish_angle));
  for(unsigned i=0;i<GM_COLUMNS;i++)assert(isfinite(w.surface[i])&&isfinite(w.velocity[i]));
 }
 assert(w.surface[0]>w.surface[GM_COLUMNS-1]);
 for(unsigned t=0;t<800;t++)gm_step(&w,-.4f,1,.01f);
 assert(w.surface[0]<w.surface[GM_COLUMNS-1]);assert(fabsf(gm_water_volume(&w)-volume)<1.0f);
 w.sequence=99;assert(gm_encode(&w,packet,sizeof packet)>0);assert(!gm_decode(&decoded,packet,sizeof packet));assert(decoded.sequence==99&&fabsf(gm_water_volume(&decoded)-volume)<1);
 for(unsigned i=0;i<GM_COLUMNS;i++)assert(fabsf(w.surface[i]-decoded.surface[i])<.006f);
 float x,y;gm_map_tilt(1,0,1,1,1,&x,&y);assert(x==0&&y==1);gm_map_tilt(1,2,0,-1,1,&x,&y);assert(x== -1&&y==2);gm_map_tilt(1,2,0,1,-1,&x,&y);assert(x==1&&y== -2);
 struct gm_layout invalid=layout;invalid.offset=90;assert(!gm_layout_valid(&invalid));
 static uint16_t fast[32*32],scratch[16*16],reference[16*16];struct gm_view view={0,0,40,40,32,32},half=view;half.width=half.height=16;
 gm_render(reference,&half,&w,0);assert(!gm_render_fast(fast,&view,&w,0,scratch,16*16));
 for(unsigned yy=0;yy<16;yy++)for(unsigned xx=0;xx<16;xx++){uint16_t q=reference[yy*16+xx];unsigned at=yy*64+xx*2;assert(fast[at]==q&&fast[at+1]==q&&fast[at+32]==q&&fast[at+33]==q);}
 assert(gm_render_fast(fast,&view,&w,0,scratch,255));view.width=31;assert(gm_render_fast(fast,&view,&w,0,scratch,256));
 puts("Aqua Link calm: conserved volume, bounded waves, correct slope response, AQF3 quantization, independent axes and fast render passed");return 0;
}
