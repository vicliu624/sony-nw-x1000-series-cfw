#include "marble.h"
#include <math.h>
#include <string.h>
static float clamp(float v,float a,float b){return v<a?a:v>b?b:v;}
float gm_radius(unsigned i){return 2.1f+(float)((i*7u)%9u)*.23f;}
int gm_layout_valid(const struct gm_layout *l){
 return l&&isfinite(l->mw)&&isfinite(l->mh)&&isfinite(l->xw)&&isfinite(l->xh)&&isfinite(l->gap)&&isfinite(l->offset)&&
 l->mw>=30&&l->mw<=100&&l->mh>=30&&l->mh<=100&&l->xw>=25&&l->xw<=100&&l->xh>=30&&l->xh<=150&&l->gap>=0&&l->gap<=50&&
 l->offset>=-150&&l->offset<=100&&fminf(l->mh,l->offset+l->xh)-fmaxf(0,l->offset)>10;
}
void gm_init(struct gm_world *s,const struct gm_layout *l,uint32_t session){
 memset(s,0,sizeof *s);s->layout=*l;s->session=session?session:1;
 for(unsigned i=0;i<GM_COUNT;i++){s->ball[i].x=4.5f+(i%4)*(l->mw-9)/3;s->ball[i].y=4.5f+(i/4)*(l->mh-9)/4;}
}
static void walls(struct gm_world *s,unsigned id){
 const struct gm_layout *l=&s->layout;float a=l->mw,b=a+l->gap,c=b+l->xw;
 float lo=fmaxf(0,l->offset),hi=fminf(l->mh,l->offset+l->xh),oy=l->offset;
 float x[]={0,a,a,b,b,c,c,b,b,a,a,0};
 float y[]={0,0,lo,lo,oy,oy,oy+l->xh,oy+l->xh,hi,hi,l->mh,l->mh};
 struct gm_ball *p=&s->ball[id];float radius=gm_radius(id);
 for(unsigned k=0;k<12;k++){
  unsigned j=(k+1)%12;float dx=x[j]-x[k],dy=y[j]-y[k],len=dx*dx+dy*dy;if(len<.0001f)continue;
  float t=clamp(((p->x-x[k])*dx+(p->y-y[k])*dy)/len,0,1);
  float nx=p->x-x[k]-t*dx,ny=p->y-y[k]-t*dy,d2=nx*nx+ny*ny;
  if(d2>=radius*radius)continue;
  float d=sqrtf(d2);if(d<.0001f){float inv=1/sqrtf(len);nx=-dy*inv;ny=dx*inv;d=0;}else{nx/=d;ny/=d;}
  p->x+=nx*(radius-d+.001f);p->y+=ny*(radius-d+.001f);
  float vn=p->vx*nx+p->vy*ny;if(vn<0){p->vx-=1.68f*vn*nx;p->vy-=1.68f*vn*ny;}
 }
}
void gm_step(struct gm_world *s,float gx,float gy,float dt){
 if(!s||!gm_layout_valid(&s->layout)||!isfinite(gx)||!isfinite(gy)||!isfinite(dt)||dt<=0)return;
 dt=fminf(dt,.04f);unsigned steps=(unsigned)ceilf(dt/.002f);float h=dt/steps;
 gx=clamp(gx,-2,2)*981;gy=clamp(gy,-2,2)*981;
 for(unsigned step=0;step<steps;step++){
  for(unsigned i=0;i<GM_COUNT;i++){struct gm_ball *p=&s->ball[i];p->vx=clamp((p->vx+gx*h)*(1-.8f*h),-350,350);p->vy=clamp((p->vy+gy*h)*(1-.8f*h),-350,350);p->x+=p->vx*h;p->y+=p->vy*h;}
  for(unsigned pass=0;pass<4;pass++){
   for(unsigned i=0;i<GM_COUNT;i++)for(unsigned j=i+1;j<GM_COUNT;j++){
    struct gm_ball *a=&s->ball[i],*b=&s->ball[j];float dx=b->x-a->x,dy=b->y-a->y,r=gm_radius(i)+gm_radius(j),d2=dx*dx+dy*dy;
    if(d2>=r*r)continue;
    float d=sqrtf(d2),nx=d>.0001f?dx/d:1,ny=d>.0001f?dy/d:0;
    float ma=gm_radius(i)*gm_radius(i),mb=gm_radius(j)*gm_radius(j),wa=mb/(ma+mb),wb=1-wa;
    a->x-=nx*(r-d)*wa;a->y-=ny*(r-d)*wa;b->x+=nx*(r-d)*wb;b->y+=ny*(r-d)*wb;
    float vn=(b->vx-a->vx)*nx+(b->vy-a->vy)*ny;if(vn<0){a->vx+=1.82f*vn*wa*nx;a->vy+=1.82f*vn*wa*ny;b->vx-=1.82f*vn*wb*nx;b->vy-=1.82f*vn*wb*ny;}
   }
   for(unsigned i=0;i<GM_COUNT;i++)walls(s,i);
  }
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
 memset(p,0,GM_PACKET);memcpy(p,"GMB1",4);put32(p+4,s->session);put32(p+8,s->sequence);p[12]=GM_COUNT;
 const float values[]={s->layout.mw,s->layout.mh,s->layout.xw,s->layout.xh,s->layout.gap,s->layout.offset};
 for(unsigned i=0;i<6;i++)put16(p+16+i*2,(int)lroundf(values[i]*100));
 for(unsigned i=0;i<GM_COUNT;i++){
  const struct gm_ball *b=&s->ball[i];const float v[]={b->x,b->y,b->vx,b->vy};
  for(unsigned k=0;k<4;k++){float z=v[k]*(k<2?100:10);if(!isfinite(z)||z< -32767||z>32767)return -1;put16(p+36+i*8+k*2,(int)lroundf(z));}
 }
 put32(p+GM_PACKET-4,crc(p,GM_PACKET-4));return GM_PACKET;
}
int gm_decode(struct gm_world *s,const uint8_t *p,size_t n){
 if(!s||!p||n!=GM_PACKET||memcmp(p,"GMB1",4)||p[12]!=GM_COUNT||p[13]||p[14]||p[15]||get32(p+GM_PACKET-4)!=crc(p,GM_PACKET-4))return -1;
 struct gm_world v;memset(&v,0,sizeof v);v.session=get32(p+4);v.sequence=get32(p+8);
 float *fields[]={&v.layout.mw,&v.layout.mh,&v.layout.xw,&v.layout.xh,&v.layout.gap,&v.layout.offset};
 for(unsigned i=0;i<6;i++)*fields[i]=(float)(int16_t)get16(p+16+i*2)/100;
 if(!v.session||!gm_layout_valid(&v.layout))return -1;
 for(unsigned i=28;i<36;i++)if(p[i])return -1;
 for(unsigned i=0;i<GM_COUNT;i++){
  struct gm_ball *b=&v.ball[i];b->x=(float)(int16_t)get16(p+36+i*8)/100;b->y=(float)(int16_t)get16(p+38+i*8)/100;
  b->vx=(float)(int16_t)get16(p+40+i*8)/10;b->vy=(float)(int16_t)get16(p+42+i*8)/10;
  if(b->x< -5||b->x>v.layout.mw+v.layout.gap+v.layout.xw+5||b->y<fminf(0,v.layout.offset)-5||b->y>fmaxf(v.layout.mh,v.layout.offset+v.layout.xh)+5)return -1;
 }
 *s=v;return 0;
}
/* Elliptical pixel footprint preserves circular physical size with unequal DPI. */
void gm_render(uint16_t *pixels,const struct gm_view *v,const struct gm_world *s,float predict){
 static const uint8_t colors[8][3]={{35,206,245},{248,87,125},{251,178,58},{131,102,246},{61,224,166},{241,105,230},{92,157,255},{218,235,112}};
 for(int y=0;y<v->height;y++)for(int x=0;x<v->width;x++){unsigned shade=(unsigned)(y*10/v->height);pixels[y*v->width+x]=(uint16_t)(((2+shade/3)<<11)|((5+shade)<<5)|(10+shade));}
 predict=clamp(predict,0,.08f);
 for(unsigned i=0;i<GM_COUNT;i++){
  float radius=gm_radius(i),cx=(s->ball[i].x+s->ball[i].vx*predict-v->x)*v->width/v->w,cy=(s->ball[i].y+s->ball[i].vy*predict-v->y)*v->height/v->h;
  float rx=radius*v->width/v->w,ry=radius*v->height/v->h;
  int left=(int)floorf(cx-rx-2),right=(int)ceilf(cx+rx+2),top=(int)floorf(cy-ry-2),bottom=(int)ceilf(cy+ry+2);
  if(left<0)left=0;
  if(top<0)top=0;
  if(right>=v->width)right=v->width-1;
  if(bottom>=v->height)bottom=v->height-1;
  for(int y=top;y<=bottom;y++)for(int x=left;x<=right;x++){
   /* Fixed-point lighting avoids per-pixel soft-float transcendental calls. */
   int u=(int)((x+.5f-cx)*256/rx),w=(int)((y+.5f-cy)*256/ry),q=(u*u+w*w)/256;if(q>256)continue;
   int rim=q;for(unsigned k=0;k<4;k++)rim=rim*q/256;
   int light=210-q*3/8-u*46/256-w*61/256;
   if(light<0)light=0;
   if(light>256)light=256;
   int spot=256-((u+82)*(u+82)+(w+97)*(w+97))/30;
   if(spot<0)spot=0;
   int spec=spot*spot/300;
   unsigned c[3];for(unsigned k=0;k<3;k++){int value=colors[i%8][k]*light/256+rim*65/256+spec;c[k]=(unsigned)(value>255?255:value);}
   pixels[y*v->width+x]=(uint16_t)(((c[0]>>3)<<11)|((c[1]>>2)<<5)|(c[2]>>3));
  }
 }
}
