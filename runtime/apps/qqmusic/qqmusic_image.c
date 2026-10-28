#include "qqmusic_image.h"
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef union {size_t bytes;long double alignment;} allocation_header;
static size_t heap_used;
static int busy;
static void *image_malloc(size_t n) {
 allocation_header *p;if(!n) n=1;
 if(n>16777216-sizeof(*p)||heap_used>16777216-n-sizeof(*p)) return 0;
 p=malloc(n+sizeof(*p));if(!p) return 0;p->bytes=n;heap_used+=n+sizeof(*p);return p+1;
}
static void image_free(void *ptr) {if(ptr) {allocation_header *p=(allocation_header *)ptr-1;heap_used-=p->bytes+sizeof(*p);free(p);}}
static void *image_realloc(void *ptr,size_t n) {
 allocation_header *p,*next;size_t without;
 if(!ptr) return image_malloc(n);
 if(!n) {image_free(ptr);return 0;}
 p=(allocation_header *)ptr-1;without=heap_used-p->bytes-sizeof(*p);
 if(n>16777216-sizeof(*p)||without>16777216-n-sizeof(*p)) return 0;
 next=realloc(p,n+sizeof(*p));if(!next) return 0;next->bytes=n;heap_used=without+n+sizeof(*p);return next+1;
}
#define STBI_MALLOC image_malloc
#define STBI_REALLOC image_realloc
#define STBI_FREE image_free
#define STBIW_MALLOC image_malloc
#define STBIW_REALLOC image_realloc
#define STBIW_FREE image_free
#define STBI_ONLY_JPEG
#define STBI_ONLY_PNG
#define STBI_NO_GIF
#define STBI_NO_STDIO
#define STBI_NO_HDR
#define STBI_NO_LINEAR
#define STBI_NO_SIMD
#define STBI_NO_THREAD_LOCALS
#define STBI_MAX_DIMENSIONS 1024
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STBI_WRITE_NO_STDIO
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
static uint32_t be32(const unsigned char *p) {return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static int png_valid(const unsigned char *data,size_t n) {
 size_t at=8;
 if(n<33||memcmp(data,"\x89PNG\r\n\x1a\n",8)) return 0;
 while(n-at>=12) {
  uint32_t length=be32(data+at),crc=0xffffffff;size_t i;unsigned bit;
  if(length>n-at-12||(at==8&&(length!=13||memcmp(data+at+4,"IHDR",4)))) return 0;
  for(i=at+4;i<at+8+length;i++) {crc^=data[i];for(bit=0;bit<8;bit++) crc=(crc>>1)^(0xedb88320u&-(crc&1u));}
  if((crc^0xffffffff)!=be32(data+at+8+length)) return 0;
  if(!memcmp(data+at+4,"IEND",4)) return !length&&at+12==n;
  at+=12+length;
 }return 0;
}
static int baseline(const unsigned char *data,size_t n) {
 size_t at=2;int found=0;
 while(at+1<n) {
  unsigned marker;uint32_t length;
  if(data[at++]!=255) return 0;
  while(at<n&&data[at]==255) at++;
  if(at==n) return 0;
  marker=data[at++];
  if(marker==0xda) return found;
  if(marker==0xd8||(marker>=0xd0&&marker<=0xd7)) continue;
  if(at+2>n) return 0;
  length=(uint32_t)data[at]<<8|data[at+1];
  if(length<2||length>n-at) return 0;
  if(marker>=0xc0&&marker<=0xcf&&marker!=0xc4&&marker!=0xc8&&marker!=0xcc) {if(marker!=0xc0) return 0;found=1;}
  at+=length;
 }return 0;
}
struct image_writer {unsigned char *out;size_t used,cap;int failed;};
static void output(void *opaque,void *data,int n) {
 struct image_writer *w=opaque;if(w->failed) return;
 if(n<0||(size_t)n>w->cap-w->used) {w->failed=1;return;}
 memcpy(w->out+w->used,data,(size_t)n);w->used+=(size_t)n;
}
int qq_image_jpeg(const unsigned char *data,size_t n,unsigned char *out,size_t cap,size_t *bytes,unsigned *width,unsigned *height) {
 unsigned char *pixels=0;int w,h,components,rc=-1,is_jpeg;size_t i;struct image_writer writer;
 if(bytes) *bytes=0;
 if(width) *width=0;
 if(height) *height=0;
 if(!data||!n||n>524288||!out||!cap||cap>524288||!bytes||!width||!height||busy||heap_used) return -1;
 memset(out,0,cap);busy=1;is_jpeg=n>=4&&data[0]==255&&data[1]==216;
 if(is_jpeg) {if(data[n-2]!=255||data[n-1]!=217) goto done;}else if(!png_valid(data,n)) goto done;
 if(!stbi_info_from_memory(data,(int)n,&w,&h,&components)||w<1||h<1||w>1024||h>1024) goto done;
 pixels=stbi_load_from_memory(data,(int)n,&w,&h,&components,is_jpeg?3:4);if(!pixels) goto done;
 if(is_jpeg&&baseline(data,n)) {if(n>cap) goto done;memcpy(out,data,n);*bytes=n;}
 else {
  if(!is_jpeg)for(i=0;i<(size_t)w*(unsigned)h;i++) {unsigned c,alpha=pixels[i*4+3];for(c=0;c<3;c++) pixels[i*3+c]=(unsigned char)((pixels[i*4+c]*alpha+255u*(255u-alpha)+127u)/255u);}
  writer.out=out;writer.used=0;writer.cap=cap;writer.failed=0;
  if(!stbi_write_jpg_to_func(output,&writer,w,h,3,pixels,90)||writer.failed) goto done;
  *bytes=writer.used;
 }
 *width=(unsigned)w;*height=(unsigned)h;rc=0;
done:
 stbi_image_free(pixels);busy=0;if(heap_used) rc=-1;
 if(rc) {memset(out,0,cap);*bytes=0;*width=*height=0;}
 return rc;
}

int qq_image_qr(const unsigned char *data,size_t n,unsigned short *out,size_t cap,unsigned *width,unsigned *height) {
 unsigned char *pixels=0;int w=0,h=0,components,rc=-1;size_t i,count=0;
 if(width)*width=0;
 if(height)*height=0;
 if(!out||!cap||cap>QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE||!width||!height||busy||heap_used)return -1;
 memset(out,0,cap*sizeof(*out));
 if(!data||!n||n>65536||!png_valid(data,n))return -1;
 busy=1;
 if(!stbi_info_from_memory(data,(int)n,&w,&h,&components)||w<21||h!=w||w>(int)QQ_IMAGE_QR_SIDE||(size_t)w*(unsigned)h>cap)goto done;
 pixels=stbi_load_from_memory(data,(int)n,&w,&h,&components,4);if(!pixels)goto done;
 if(w<21||h!=w||w>(int)QQ_IMAGE_QR_SIDE||(size_t)w*(unsigned)h>cap)goto done;
 count=(size_t)w*(unsigned)h;
 for(i=0;i<count;i++) {
  unsigned alpha=pixels[i*4+3],r=(pixels[i*4]*alpha+255u*(255u-alpha)+127u)/255u;
  unsigned g=(pixels[i*4+1]*alpha+255u*(255u-alpha)+127u)/255u,b=(pixels[i*4+2]*alpha+255u*(255u-alpha)+127u)/255u;
  out[i]=(unsigned short)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
 }
 *width=(unsigned)w;*height=(unsigned)h;rc=0;
done:
 if(pixels) {volatile unsigned char *erase=pixels;size_t bytes=(size_t)(w>0?w:0)*(unsigned)(h>0?h:0)*4;while(bytes--)*erase++=0;}
 stbi_image_free(pixels);busy=0;if(heap_used)rc=-1;
 if(rc){memset(out,0,cap*sizeof(*out));*width=*height=0;}
 return rc;
}

int qq_image_thumbnail(const unsigned char *data,size_t n,unsigned short *out,unsigned side){
 unsigned char *pixels=0;int w=0,h=0,components,rc=-1;unsigned x,y;
 if(!data||!n||n>262144||!out||!side||side>96||busy||heap_used)return -1;
 busy=1;
 if(!stbi_info_from_memory(data,(int)n,&w,&h,&components)||w<1||h<1||w>512||h>512)goto done;
 pixels=stbi_load_from_memory(data,(int)n,&w,&h,&components,4);if(!pixels)goto done;
 for(y=0;y<side;y++)for(x=0;x<side;x++){
  const unsigned char *p=pixels+((size_t)(y*(unsigned)h/side)*(unsigned)w+x*(unsigned)w/side)*4;unsigned a=p[3],r=(p[0]*a+255*(255-a)+127)/255,g=(p[1]*a+255*(255-a)+127)/255,b=(p[2]*a+255*(255-a)+127)/255;
  out[y*side+x]=(unsigned short)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
 }rc=0;
 done:stbi_image_free(pixels);busy=0;if(heap_used)rc=-1;if(rc)memset(out,0,(size_t)side*side*2);return rc;
}
