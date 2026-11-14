#include "qqmusic_image.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static int decode(const char *s,size_t n,unsigned char *out,size_t cap,size_t *bytes) {
 size_t i,used=0,digits=0,padding=0;unsigned acc=0,bits=0;
 for(i=0;i<n;i++) {
  unsigned c=(unsigned char)s[i],v;
  if(c=='=') {padding++;continue;}if(padding) return -1;
  if(c>='A'&&c<='Z') v=c-'A';else if(c>='a'&&c<='z') v=c-'a'+26;else if(c>='0'&&c<='9') v=c-'0'+52;else if(c=='+') v=62;else if(c=='/') v=63;else return -1;
  digits++;acc=(acc<<6)|v;bits+=6;
  if(bits>=8) {bits-=8;if(used==cap) return -1;out[used++]=(unsigned char)(acc>>bits);acc&=(1u<<bits)-1;}
 }
 if(!digits||digits%4==1||padding>2||(padding&&(padding!=(4-digits%4)%4||n%4))||acc) return -1;
 *bytes=used;return 0;
}
static int word(const unsigned char *p,size_t n,size_t *at,uint32_t *value) {
 if(n-*at<4) return -1;
 *value=(uint32_t)p[*at]<<24|(uint32_t)p[*at+1]<<16|(uint32_t)p[*at+2]<<8|p[*at+3];*at+=4;return 0;
}
int qq_picture_jpeg(const char *encoded,size_t n,unsigned char *out,size_t cap,size_t *bytes,unsigned *width,unsigned *height) {
 unsigned char *raw=0;size_t decoded=0,at=0,mime_at;uint32_t type,mime,description,w,h,depth,colors,image;int rc=-1;
 if(bytes) *bytes=0;
 if(width) *width=0;
 if(height) *height=0;
 if(!encoded||!n||n>1048576||!out||!cap||cap>524288||!bytes||!width||!height) return -1;
 raw=malloc(n*3/4+3);if(!raw) return -1;
 if(decode(encoded,n,raw,n*3/4+3,&decoded)||word(raw,decoded,&at,&type)||word(raw,decoded,&at,&mime)||mime>64||mime>decoded-at) goto done;
 mime_at=at;at+=mime;
 if(word(raw,decoded,&at,&description)||description>4096||description>decoded-at) goto done;
 at+=description;
 if(word(raw,decoded,&at,&w)||word(raw,decoded,&at,&h)||word(raw,decoded,&at,&depth)||word(raw,decoded,&at,&colors)||word(raw,decoded,&at,&image)||image!=decoded-at||image>524288) goto done;
 if(type!=3) {rc=1;goto done;}
 if(!((mime==10&&!memcmp(raw+mime_at,"image/jpeg",10))||(mime==9&&!memcmp(raw+mime_at,"image/png",9)))) goto done;
 if((mime==10&&(image<2||raw[at]!=255||raw[at+1]!=216))||(mime==9&&(image<8||memcmp(raw+at,"\x89PNG\r\n\x1a\n",8)))) goto done;
 if(qq_image_jpeg(raw+at,image,out,cap,bytes,width,height)||(w&&w!=*width)||(h&&h!=*height)) goto done;
 rc=0;
done:
 free(raw);if(rc<0) {memset(out,0,cap);*bytes=0;*width=*height=0;}return rc;
}
