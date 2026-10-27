#include "epub.h"
#include <stdlib.h>
#include <string.h>
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_JPEG
#define STBI_ONLY_PNG
#define STBI_NO_STDIO
#define STBI_NO_HDR
#define STBI_NO_LINEAR
#define STBI_NO_THREAD_LOCALS
#define STBI_MAX_DIMENSIONS 4096
#include "../../../../third_party/epub-stb/stb_image.h"
void ep_drop_image(struct ep_book*b){free(b->cached_image);b->cached_image=0;b->cached_id=-1;b->cached_w=b->cached_h=0;}
static unsigned lerp(unsigned a,unsigned b,unsigned t){return (a*(256-t)+b*t+128)>>8;}
static void sample(const unsigned char*src,int width,int height,int fx,int fy,unsigned char out[4]){if(fx<0)fx=0;if(fy<0)fy=0;int x=fx>>16,y=fy>>16;if(x>=width)x=width-1;if(y>=height)y=height-1;int xx=x+1<width?x+1:x,yy=y+1<height?y+1:y;unsigned wx=(fx>>8)&255,wy=(fy>>8)&255;const unsigned char*a=src+(y*width+x)*4,*b=src+(y*width+xx)*4,*c=src+(yy*width+x)*4,*d=src+(yy*width+xx)*4;unsigned alpha=lerp(lerp(a[3],b[3],wx),lerp(c[3],d[3],wx),wy);out[3]=(unsigned char)alpha;for(unsigned k=0;k<3;k++){unsigned v=lerp(lerp(a[k]*a[3],b[k]*b[3],wx),lerp(c[k]*c[3],d[k]*d[3],wx),wy);out[k]=alpha?(unsigned char)(v/alpha):0;}}
int ep_image_info(struct ep_book*b,unsigned id,unsigned*w,unsigned*h){if(id>=b->doc->image_count)return 0;struct ep_image*r=b->doc->images+id;if(!r->width){unsigned n;unsigned char*data=ez_read(&b->zip,r->path,8*1024*1024,&n);if(!data)return 0;int x=0,y=0,c=0;int ok=stbi_info_from_memory(data,(int)n,&x,&y,&c);free(data);if(!ok||x<=0||y<=0||x>4096||y>4096||(uint64_t)x*y>4000000)return 0;r->width=(unsigned)x;r->height=(unsigned)y;}*w=r->width;*h=r->height;return 1;}
unsigned char*ep_pixels(struct ep_book*b,unsigned id,int*w,int*h){if(b->cached_id==(int)id&&b->cached_image){*w=b->cached_w;*h=b->cached_h;return b->cached_image;}unsigned width,height;if(!ep_image_info(b,id,&width,&height))return 0;unsigned n;unsigned char*data=ez_read(&b->zip,b->doc->images[id].path,8*1024*1024,&n);if(!data)return 0;int x=0,y=0,c=0;unsigned char*p=stbi_load_from_memory(data,(int)n,&x,&y,&c,4);free(data);if(!p)return 0;int dw=x,dh=y;if(dw>224){dh=(int)((int64_t)dh*224/dw);dw=224;}if(dh>300){dw=(int)((int64_t)dw*300/dh);dh=300;}if(dw<1)dw=1;if(dh<1)dh=1;
 if(dw!=x||dh!=y){unsigned char*q=malloc((size_t)dw*dh*4);if(!q){stbi_image_free(p);return 0;}int sx=(x<<16)/dw,sy=(y<<16)/dh;for(int j=0;j<dh;j++)for(int i=0;i<dw;i++)sample(p,x,y,i*sx+sx/2-32768,j*sy+sy/2-32768,q+(j*dw+i)*4);stbi_image_free(p);p=q;}
 ep_drop_image(b);b->cached_id=(int)id;b->cached_w=dw;b->cached_h=dh;b->cached_image=p;*w=dw;*h=dh;return p;
}
void ep_image_draw(struct ep_book*b,unsigned id,uint16_t*surface,int x,int y,int width,int height){int sw,sh;unsigned char*p=ep_pixels(b,id,&sw,&sh);if(!p){for(int j=0;j<height;j++)for(int i=0;i<width;i++)if((j==0||i==0||j==height-1||i==width-1)&&x+i>=0&&x+i<240&&y+j>=0&&y+j<432)surface[(y+j)*240+x+i]=0x8410;return;}int sx=(sw<<16)/width,sy=(sh<<16)/height;for(int j=0;j<height;j++)for(int i=0;i<width;i++){if(x+i<0||x+i>=240||y+j<0||y+j>=432)continue;unsigned char v[4];sample(p,sw,sh,i*sx+sx/2-32768,j*sy+sy/2-32768,v);unsigned a=v[3];uint16_t bg=surface[(y+j)*240+x+i];unsigned r=((bg>>11)*255/31*(255-a)+(unsigned)v[0]*a)/255,g=(((bg>>5)&63)*255/63*(255-a)+(unsigned)v[1]*a)/255,bl=((bg&31)*255/31*(255-a)+(unsigned)v[2]*a)/255;surface[(y+j)*240+x+i]=(uint16_t)((r>>3)<<11|(g>>2)<<5|(bl>>3));}}
