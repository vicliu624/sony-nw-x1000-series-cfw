#include "../../runtime/apps/glass-marble/marble.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static struct gm_layout layout={40,40,37,66.6f,8,-13.3f};
static int inside(const struct gm_ball *b){
 return (b->x>=0&&b->x<=40&&b->y>=0&&b->y<=40)||(b->x>=40&&b->x<=48&&b->y>=0&&b->y<=40)||(b->x>=48&&b->x<=85&&b->y>=-13.3f&&b->y<=53.3f);
}
int main(int argc,char **argv){
 struct gm_world w,decoded;uint8_t packet[GM_PACKET];gm_init(&w,&layout,123);
 if(argc==2){
  (void)argv;for(unsigned i=0;i<GM_COUNT;i++){w.ball[i].x=25+(i%6)*9;w.ball[i].y=3+(i/6)*10;}
  static uint16_t m[480*480],x[240*432];struct gm_view mv={0,0,40,40,480,480},xv={48,-13.3f,37,66.6f,240,432};gm_render(m,&mv,&w,0);gm_render(x,&xv,&w,0);
  if(fwrite(m,2,480*480,stdout)!=480*480||fwrite(x,2,240*432,stdout)!=240*432)return 1;
  return 0;
 }
 assert(GM_PACKET<=250);assert(gm_encode(&w,packet,sizeof packet)==GM_PACKET);assert(!gm_decode(&decoded,packet,sizeof packet));assert(decoded.session==123);
 struct gm_world saved=decoded;packet[57]^=1;assert(gm_decode(&decoded,packet,sizeof packet));assert(!memcmp(&saved,&decoded,sizeof saved));packet[57]^=1;
 assert(gm_decode(&decoded,packet,sizeof packet-1));assert(gm_newer(0,0xffffffffu));assert(!gm_newer(7,7));assert(!gm_newer(6,7));
 /* A complete snapshot can skip arbitrarily many intermediate updates. */
 w.sequence=99;w.ball[3].x=62;assert(gm_encode(&w,packet,sizeof packet)>0);assert(!gm_decode(&decoded,packet,sizeof packet));assert(decoded.ball[3].x==62&&decoded.sequence==99);
 gm_init(&w,&layout,1);
 for(unsigned t=0;t<1600;t++){
  gm_step(&w,.4f,.02f,.01f);
  for(unsigned i=0;i<GM_COUNT;i++){assert(isfinite(w.ball[i].x)&&isfinite(w.ball[i].y));assert(inside(&w.ball[i]));}
 }
 unsigned right=0;for(unsigned i=0;i<GM_COUNT;i++)right+=w.ball[i].x>48;assert(right>=15);
 for(unsigned t=0;t<1600;t++)gm_step(&w,-.4f,0,.01f);
 unsigned left=0;for(unsigned i=0;i<GM_COUNT;i++)left+=w.ball[i].x<40;assert(left>=15);
 /* Equal physical diameter despite different pixel radii. */
 float radius=gm_radius(8),m_px=radius*480/40,x_px=radius*240/37;assert(fabsf(m_px*40/480-x_px*37/240)<.00001f);
 struct gm_layout invalid=layout;invalid.offset=90;assert(!gm_layout_valid(&invalid));
 puts("Glass Marble: wire integrity, complete snapshots, sequence wrap, finite physics, round-trip seam transfer and physical scale passed");return 0;
}
