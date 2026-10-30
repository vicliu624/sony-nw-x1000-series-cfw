#include "marble.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>
static float clamp(float v,float a,float b){return v<a?a:v>b?b:v;}
int gm_layout_valid(const struct gm_layout *l){
 return l&&isfinite(l->mw)&&isfinite(l->mh)&&isfinite(l->xw)&&isfinite(l->xh)&&isfinite(l->gap)&&isfinite(l->offset)&&
 l->mw>=30&&l->mw<=100&&l->mh>=30&&l->mh<=100&&l->xw>=25&&l->xw<=100&&l->xh>=30&&l->xh<=150&&l->gap>=0&&l->gap<=50&&
 l->offset>=-150&&l->offset<=100&&fminf(l->mh,l->offset+l->xh)-fmaxf(0,l->offset)>10;
}
static void column_bounds(const struct gm_layout *l,float x,float *top,float *bottom){
 if(x<l->mw){*top=0;*bottom=l->mh;}
 else if(x<l->mw+l->gap){*top=fmaxf(0,l->offset);*bottom=fminf(l->mh,l->offset+l->xh);}
 else{*top=l->offset;*bottom=l->offset+l->xh;}
}
float gm_surface_y(const struct gm_world *s,float x){
 float width=s->layout.mw+s->layout.gap+s->layout.xw,u=x/width*GM_COLUMNS-.5f;
 if(u<=0)return s->surface[0];
 if(u>=GM_COLUMNS-1)return s->surface[GM_COLUMNS-1];
 unsigned i=(unsigned)u;return s->surface[i]+(s->surface[i+1]-s->surface[i])*(u-i);
}
static float volume_at(const struct gm_world *s,float offset){
 float width=s->layout.mw+s->layout.gap+s->layout.xw,dx=width/GM_COLUMNS,sum=0;
 for(unsigned i=0;i<GM_COLUMNS;i++){float top,bottom;column_bounds(&s->layout,(i+.5f)*dx,&top,&bottom);sum+=clamp(bottom-s->surface[i]-offset,0,bottom-top)*dx;}
 return sum;
}
float gm_water_volume(const struct gm_world *s){return volume_at(s,0);}
static void conserve_volume(struct gm_world *s){
 float low=-512,high=512,width=s->layout.mw+s->layout.gap+s->layout.xw;
 for(unsigned n=0;n<20;n++){float middle=(low+high)*.5f;if(volume_at(s,middle)>s->volume)low=middle;else high=middle;}
 float offset=(low+high)*.5f;
 for(unsigned i=0;i<GM_COLUMNS;i++){float top,bottom;column_bounds(&s->layout,(i+.5f)*width/GM_COLUMNS,&top,&bottom);s->surface[i]=clamp(s->surface[i]+offset,top,bottom);}
}
void gm_init(struct gm_world *s,const struct gm_layout *l,uint32_t session){
 memset(s,0,sizeof *s);s->layout=*l;s->session=session?session:1;s->swim_direction=1;
 float width=l->mw+l->gap+l->xw,area=0;
 for(unsigned i=0;i<GM_COLUMNS;i++){float top,bottom;column_bounds(l,(i+.5f)*width/GM_COLUMNS,&top,&bottom);area+=(bottom-top)*width/GM_COLUMNS;s->surface[i]=0;}
 s->volume=area*.38f;conserve_volume(s);s->fish_x=l->mw*.5f;s->fish_y=gm_surface_y(s,s->fish_x)+6;
}
void gm_map_tilt(float ax,float ay,unsigned rotation,int flip_x,int flip_y,float *x,float *y){
 for(unsigned k=0;k<(rotation&3u);k++){float t=ax;ax=-ay;ay=t;}
 *x=ax*(flip_x<0?-1:1);*y=ay*(flip_y<0?-1:1);
}
void gm_step(struct gm_world *s,float gx,float gy,float dt){
 if(!s||!gm_layout_valid(&s->layout)||!isfinite(gx)||!isfinite(gy)||!isfinite(dt)||dt<=0)return;
 dt=fminf(dt,.05f);unsigned steps=(unsigned)ceilf(dt/.01f);float h=dt/steps,width=s->layout.mw+s->layout.gap+s->layout.xw;
 float wanted=clamp(gx/fmaxf(gy,.35f),-.65f,.65f)*.45f;
 for(unsigned step=0;step<steps;step++){
  s->slope+=(wanted-s->slope)*h/(.35f+h);
  static float target[GM_COLUMNS],before[GM_COLUMNS];float low=-256,high=256;
  for(unsigned n=0;n<18;n++){
   float level=(low+high)*.5f,volume=0;
   for(unsigned i=0;i<GM_COLUMNS;i++){float top,bottom;column_bounds(&s->layout,(i+.5f)*width/GM_COLUMNS,&top,&bottom);float y=level-s->slope*((i+.5f)*width/GM_COLUMNS-width*.5f);volume+=clamp(bottom-y,0,bottom-top)*width/GM_COLUMNS;}
   if(volume>s->volume)low=level;else high=level;
  }
  float level=(low+high)*.5f;
  memcpy(before,s->surface,sizeof before);
  for(unsigned i=0;i<GM_COLUMNS;i++){
   float top,bottom,x=(i+.5f)*width/GM_COLUMNS;column_bounds(&s->layout,x,&top,&bottom);
   target[i]=clamp(level-s->slope*(x-width*.5f)+.10f*sinf(i*.55f+s->fish_phase*.2f),top,bottom);
   float curvature=before[i?i-1:i]+before[i+1<GM_COLUMNS?i+1:i]-2*before[i];
   float acceleration=22*(target[i]-before[i])+12*curvature-8*s->velocity[i];
   s->velocity[i]=clamp(s->velocity[i]+acceleration*h,-9,9);s->surface[i]=clamp(before[i]+s->velocity[i]*h,top,bottom);
  }
  conserve_volume(s);
  s->fish_phase+=h*6.5f;
  float top,bottom,surface=gm_surface_y(s,s->fish_x);column_bounds(&s->layout,s->fish_x,&top,&bottom);
  if(s->fish_x<6)s->swim_direction=1;
  if(s->fish_x>width-6)s->swim_direction=-1;
  float ahead=clamp(s->fish_x+s->swim_direction*3,2,width-2),ahead_top,ahead_bottom;column_bounds(&s->layout,ahead,&ahead_top,&ahead_bottom);
  if(ahead_bottom-gm_surface_y(s,ahead)<4.8f)s->swim_direction=-s->swim_direction;
  float depth=fmaxf(0,bottom-surface),target_y=surface+depth*(.55f+.08f*sinf(s->fish_phase*.21f));target_y=clamp(target_y,surface+2.2f,bottom-2.2f);
  float desired=atan2f((target_y-s->fish_y)*1.5f,s->swim_direction*5),difference=desired-s->fish_angle;
  while(difference>3.141593f)difference-=6.283186f;
  while(difference< -3.141593f)difference+=6.283186f;
  s->fish_angle+=clamp(difference,-1.4f*h,1.4f*h);
  if(s->fish_angle>3.141593f)s->fish_angle-=6.283186f;
  if(s->fish_angle< -3.141593f)s->fish_angle+=6.283186f;
  s->fish_x=clamp(s->fish_x+(cosf(s->fish_angle)*3.8f+s->slope*2)*h,4,width-4);
  s->fish_y+=(target_y-s->fish_y)*fminf(1,h*3);
  surface=gm_surface_y(s,s->fish_x);column_bounds(&s->layout,s->fish_x,&top,&bottom);s->fish_y=clamp(s->fish_y,fminf(surface+2,bottom-1),bottom-1);
 }
}
static void put16(uint8_t *p,int v){p[0]=(uint8_t)v;p[1]=(uint8_t)((unsigned)v>>8);}
static unsigned get16(const uint8_t *p){return p[0]|((unsigned)p[1]<<8);}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t get32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint32_t crc(const uint8_t *p,size_t n){uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=p[i];for(unsigned j=0;j<8;j++)c=(c>>1)^(0xedb88320u& (0u-(c&1u)));}return ~c;}
int gm_newer(uint32_t a,uint32_t b){return a!=b&&(uint32_t)(a-b)<0x80000000u;}
int gm_encode(const struct gm_world *s,uint8_t *p,size_t n){
 if(!s||!p||n<GM_PACKET||!gm_layout_valid(&s->layout)||!s->session)return -1;
 memset(p,0,GM_PACKET);memcpy(p,"AQF3",4);put32(p+4,s->session);put32(p+8,s->sequence);put16(p+12,GM_COLUMNS);
 const float values[]={s->layout.mw,s->layout.mh,s->layout.xw,s->layout.xh,s->layout.gap,s->layout.offset};
 for(unsigned i=0;i<6;i++)put16(p+16+i*2,(int)lroundf(values[i]*100));
 for(unsigned i=0;i<GM_COLUMNS;i++){float value=s->surface[i]*100;if(!isfinite(value)||value< -32767||value>32767)return -1;put16(p+52+i*2,(int)lroundf(value));}
 const float fish[]={s->fish_x,s->fish_y,s->fish_angle,s->fish_phase};
 for(unsigned k=0;k<4;k++){float f=fish[k]*(k<2?100:1000);if(k==3)f=fmodf(fish[k],6.2831853f)*1000;if(!isfinite(f)||f< -32767||f>65535)return -1;put16(p+36+k*2,(int)lroundf(f));}
 put32(p+GM_PACKET-4,crc(p,GM_PACKET-4));return GM_PACKET;
}
int gm_decode(struct gm_world *s,const uint8_t *p,size_t n){
 if(!s||!p||n!=GM_PACKET||memcmp(p,"AQF3",4)||get16(p+12)!=GM_COLUMNS||p[14]||p[15]||get32(p+GM_PACKET-4)!=crc(p,GM_PACKET-4))return -1;
 struct gm_world v;memset(&v,0,sizeof v);v.session=get32(p+4);v.sequence=get32(p+8);
 float *fields[]={&v.layout.mw,&v.layout.mh,&v.layout.xw,&v.layout.xh,&v.layout.gap,&v.layout.offset};
 for(unsigned i=0;i<6;i++)*fields[i]=(float)(int16_t)get16(p+16+i*2)/100;
 if(!v.session||!gm_layout_valid(&v.layout))return -1;
 for(unsigned i=28;i<36;i++)if(p[i])return -1;
 for(unsigned i=44;i<52;i++)if(p[i])return -1;
 v.fish_x=(float)(int16_t)get16(p+36)/100;v.fish_y=(float)(int16_t)get16(p+38)/100;v.fish_angle=(float)(int16_t)get16(p+40)/1000;v.fish_phase=(float)get16(p+42)/1000;
 if(v.fish_x< -5||v.fish_x>v.layout.mw+v.layout.gap+v.layout.xw+5||v.fish_y<fminf(0,v.layout.offset)-5||v.fish_y>fmaxf(v.layout.mh,v.layout.offset+v.layout.xh)+5||fabsf(v.fish_angle)>6.4f)return -1;
 for(unsigned i=0;i<GM_COLUMNS;i++){
  float top,bottom;column_bounds(&v.layout,(i+.5f)*(v.layout.mw+v.layout.gap+v.layout.xw)/GM_COLUMNS,&top,&bottom);
  v.surface[i]=(float)(int16_t)get16(p+52+i*2)/100;
  if(v.surface[i]<top-.02f||v.surface[i]>bottom+.02f)return -1;
 }
 v.volume=gm_water_volume(&v);v.swim_direction=cosf(v.fish_angle)<0?-1:1;
 *s=v;return 0;
}
/* Metaball density on a coarse physical grid creates a continuous liquid surface.
 * Rendering is integer-only per pixel on the ARM926. Both panels sample world mm. */
static uint16_t field[122*122];
static uint16_t rgb(unsigned r,unsigned g,unsigned b){return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
static void floor_rgb(int x,int y,int *r,int *g,int *b){
 unsigned tx=(unsigned)x&511u,ty=(unsigned)y&511u;
 uint32_t grain=((uint32_t)(x>>3)*73856093u)^((uint32_t)(y>>3)*19349663u);
 int variation=(int)(grain&7u)-3;
 int seam=tx<7u||ty<7u;
 int check=(int)(((unsigned)(x>>9)^(unsigned)(y>>9))&1u)*3;
 *r=193+variation+check-seam*18;*g=205+variation+check-seam*16;*b=206+variation+check-seam*13;
}
static int limit255(int x){return x<0?0:x>255?255:x;}
int gm_scale2x(uint16_t *out,int width,int height,const uint16_t *source,size_t pixels){
 if(!out||!source||width<2||height<2||(width&1)||(height&1)||pixels<(size_t)(width/2)*(size_t)(height/2))return -1;
 for(int y=0;y<height/2;y++)for(int x=0;x<width/2;x++){
  uint16_t p=source[y*(width/2)+x];int at=y*2*width+x*2;
  out[at]=out[at+1]=out[at+width]=out[at+width+1]=p;
 }return 0;
}
int gm_render_fast(uint16_t *out,const struct gm_view *view,const struct gm_world *world,float predict,uint16_t *scratch,size_t pixels){
 if(!out||!view||!world||!scratch||view->width<2||view->height<2||view->width>480||view->height>480||(view->width&1)||(view->height&1)||pixels<(size_t)(view->width/2)*(size_t)(view->height/2))return -1;
 struct gm_view half=*view;half.width/=2;half.height/=2;gm_render(scratch,&half,world,predict);
 return gm_scale2x(out,view->width,view->height,scratch,pixels);
}
void gm_render(uint16_t *pixels,const struct gm_view *v,const struct gm_world *s,float predict){
 if(!pixels||!v||!s||v->width<1||v->height<1||v->width>480||v->height>480||v->w<=0||v->h<=0)return;
 int gw=(v->width+3)/4+1,gh=(v->height+3)/4+1;memset(field,0,(size_t)(gw*gh)*sizeof field[0]);
 (void)predict;
 int row_step=(int)lroundf(4*v->h/v->height*110*256);
 for(int x=0;x<gw;x++){
  float wx=v->x+(float)(x*4)*v->w/v->width,surface=gm_surface_y(s,wx);
  int value=(int)lroundf((130+(v->y-surface)*110)*256);
  for(int y=0;y<gh;y++){
   field[y*gw+x]=(uint16_t)(value<=0?0:value>=700*256?700:value/256);
   value+=row_step;
  }
 }
 static int16_t wave[256];static int wave_ready;
 if(!wave_ready){for(unsigned i=0;i<256;i++)wave[i]=(int16_t)lroundf(sinf(i*6.2831853f/256)*256);wave_ready=1;}
 float cycle=fmodf(s->fish_phase,6.2831853f);if(cycle<0)cycle+=6.2831853f;
 int phase=(int)(cycle*(256/6.2831853f)),worldx=(int)lroundf(v->x*64),worldy=(int)lroundf(v->y*64);
 int stepx=(int)lroundf(v->w/v->width*65536),stepy=(int)lroundf(v->h/v->height*65536);
 for(int y=0;y<v->height;y++)for(int x=0;x<v->width;x++){
  int col=x/4,row=y/4,fx=x&3,fy=y&3;unsigned index=(unsigned)(row*gw+col);
  int density=(field[index]*(4-fx)*(4-fy)+field[index+1]*fx*(4-fy)+field[index+gw]*(4-fx)*fy+field[index+gw+1]*fx*fy)/16;
  int wx=worldx+x*stepx/1024,wy=worldy+y*stepy/1024,fr,fg,fb;
  floor_rgb(wx,wy,&fr,&fg,&fb);
  if(density<110){int shadow=density/22;pixels[y*v->width+x]=rgb((unsigned)(fr-shadow),(unsigned)(fg-shadow),(unsigned)(fb-shadow));continue;}
  int wa=wave[(unsigned)(wx/4+wy/7+phase)&255],wb=wave[(unsigned)(wx/9-wy/5+phase*2)&255];
  int nx=wa/7,ny=wb/7;
  if(density<350){int dx=(int)field[index+1]-(int)field[index-(col>0?1:0)],dy=(int)field[index+gw]-(int)field[index-(row>0?gw:0)];
   nx+=dx< -180?-90:dx>180?90:dx/2;ny+=dy< -180?-90:dy>180?90:dy/2;
  }
  int r,g,b;floor_rgb(wx+nx/2+wa/16,wy+ny/2+wb/16,&r,&g,&b);
  /* Clear water transmits the floor, with blue absorption and wave refraction. */
  int depth=density>700?700:density;
  r=r*(212-depth/35)/256;g=g*(246-depth/95)/256+3;b=b*253/256+13;
  int ridge=25-abs(wa+wb),caustic=ridge>0?ridge*ridge/35:0;
  int shine=nx+ny+wa/5-65;if(shine<0)shine=0;shine=shine*shine/110;if(shine>75)shine=75;
  int fresnel=density<195?(195-density)/3:0;
  r+=caustic+shine+fresnel;g+=caustic+shine+fresnel;b+=caustic/2+shine+fresnel;
  if(density<145){int coverage=(density-110)*256/35;r=(fr*(256-coverage)+r*coverage)/256;g=(fg*(256-coverage)+g*coverage)/256;b=(fb*(256-coverage)+b*coverage)/256;}
  pixels[y*v->width+x]=rgb((unsigned)limit255(r),(unsigned)limit255(g),(unsigned)limit255(b));
 }
 /* One goldfish: curved tail fan, translucent fins, scales, gill and eye. */
 float cx=(s->fish_x-v->x)*v->width/v->w,cy=(s->fish_y-v->y)*v->height/v->h;
 int left=(int)floorf(cx-8*v->width/v->w),right=(int)ceilf(cx+8*v->width/v->w),top=(int)floorf(cy-8*v->height/v->h),bottom=(int)ceilf(cy+8*v->height/v->h);
 if(left<0)left=0;
 if(top<0)top=0;
 if(right>=v->width)right=v->width-1;
 if(bottom>=v->height)bottom=v->height-1;
 int co=(int)lroundf(cosf(s->fish_angle)*256),si=(int)lroundf(sinf(s->fish_angle)*256),tail=(int)lroundf(sinf(s->fish_phase)*210);
 int mmx=(int)lroundf(v->w/v->width*65536),mmy=(int)lroundf(v->h/v->height*65536),cxi=(int)lroundf(cx*256),cyi=(int)lroundf(cy*256);
 for(int y=top;y<=bottom;y++)for(int x=left;x<=right;x++){
  int dx=(x*256+128-cxi)*mmx/65536,dy=(y*256+128-cyi)*mmy/65536;
  int u=(dx*co+dy*si)/256,w=(-dx*si+dy*co)/256;
  int tail_center=tail*(-u-650)/900;
  unsigned base=field[(y/4)*gw+x/4];if(base<110)continue;
  int body=u*u/9+w*w/3;
  uint16_t color=pixels[y*v->width+x];
  if(u< -610&&u> -1580&&abs(w-tail_center)<(-u-560)*3/5){int stripe=((w-tail_center+2048)/45)%3;color=stripe?rgb(249,133,48):rgb(255,199,106);}
  else if(u> -480&&u<180&&abs(w)<700-abs(u+100)*2/3&&abs(w)>250){color=rgb(82,155,155);}
  if(body<65536){unsigned shine=(unsigned)(256-(w<0?-w:w)/3);if(shine>256)shine=0;
   unsigned scales=(unsigned)(((u+2048)/70+(w+2048)/80)&1);color=rgb(240+scales*12,105+shine/3+scales*12,30+shine/5);
   if(u> -90&&u< -35)color=rgb(211,86,35);
   int ex=u-470,ey=w+130;if(ex*ex+ey*ey<105*105)color=rgb(10,22,27);
   ex=u-490;ey=w+155;if(ex*ex+ey*ey<34*34)color=rgb(250,255,255);
  }
  pixels[y*v->width+x]=color;
 }
}
