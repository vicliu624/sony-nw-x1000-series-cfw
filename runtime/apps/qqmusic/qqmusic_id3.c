#include "qqmusic_id3.h"
#include <stdint.h>
#include <string.h>
struct writer {unsigned char *out;size_t used,cap;};
static int put(struct writer *w,unsigned char c) {
 if(w->used==w->cap) return -1;
 w->out[w->used++]=c;return 0;
}
static int block(struct writer *w,const void *p,size_t n) {
 if(n>w->cap-w->used) return -1;
 memcpy(w->out+w->used,p,n);w->used+=n;return 0;
}
static void be32(unsigned char *p,size_t n) {p[0]=(unsigned char)(n>>24);p[1]=(unsigned char)(n>>16);p[2]=(unsigned char)(n>>8);p[3]=(unsigned char)n;}
static int unit(struct writer *w,uint32_t c) {return put(w,(unsigned char)c)||put(w,(unsigned char)(c>>8));}
static int text(struct writer *w,const char *s,int encoding_byte) {
 size_t i=0;unsigned more,j;uint32_t c,min;
 if((encoding_byte&&put(w,1))||put(w,255)||put(w,254)) return -1;
 while(s[i]) {
  if(i>=4096) return -1;
  c=(unsigned char)s[i++];
  if(c<32||c==127) return -1;
  if(c<128) {if(unit(w,c)) return -1;continue;}
  if(c>=0xc2&&c<=0xdf) {more=1;min=0x80;c&=31;}
  else if(c>=0xe0&&c<=0xef) {more=2;min=0x800;c&=15;}
  else if(c>=0xf0&&c<=0xf4) {more=3;min=0x10000;c&=7;}
  else return -1;
  for(j=0;j<more;j++) {
   unsigned char v;if(i>=4096||!s[i]) return -1;v=(unsigned char)s[i++];
   if((v&0xc0)!=0x80) return -1;
   c=(c<<6)|(v&63);
  }
  if(c<min||c>0x10ffff||(c>=0xd800&&c<=0xdfff)) return -1;
  if(c<65536) {if(unit(w,c)) return -1;}
  else {c-=0x10000;if(unit(w,0xd800+(c>>10))||unit(w,0xdc00+(c&1023))) return -1;}
 }
 return unit(w,0);
}
static int frame(struct writer *w,const char *id,const char *s) {
 size_t start=w->used;unsigned char header[10]={0};
 if(!s||!*s) return 0;
 memcpy(header,id,4);
 if(block(w,header,sizeof(header))||text(w,s,1)) return -1;
 be32(w->out+start+4,w->used-start-10);return 0;
}
static int extra(struct writer *w,const char *name,const char *value) {
 size_t start=w->used;unsigned char header[10]={'T','X','X','X',0,0,0,0,0,0};
 if(!name||!*name||!value) return -1;
 if(block(w,header,sizeof(header))||text(w,name,1)||text(w,value,0)) return -1;
 be32(w->out+start+4,w->used-start-10);return 0;
}
static int position(const char *s) {
 unsigned digits=0,slashes=0;
 if(!s||!*s) return 1;
 for(;*s;s++) {
  if(*s=='/'&&digits&&!slashes) {slashes++;digits=0;}
  else if(*s>='0'&&*s<='9'&&digits<5) digits++;
  else return 0;
 }return digits!=0;
}
int qq_id3_build(const struct qq_track_tags *t,unsigned char *out,size_t cap,size_t *bytes) {
 struct writer w;size_t n,i;
 if(bytes) *bytes=0;
 if(!out||!cap) return -1;
 memset(out,0,cap);
 if(!t||!bytes||cap<10||!position(t->track)||!position(t->disc)) return -1;
 if(t->year&&*t->year) {
  for(i=0;i<4;i++) if(t->year[i]<'0'||t->year[i]>'9') return -1;
  if(t->year[4]) return -1;
 }
 w.out=out;w.used=10;w.cap=cap<1048576?cap:1048576;
 if(frame(&w,"TIT2",t->title)||frame(&w,"TPE1",t->artist)||frame(&w,"TALB",t->album)||frame(&w,"TPE2",t->album_artist)||frame(&w,"TRCK",t->track)||frame(&w,"TPOS",t->disc)||frame(&w,"TYER",t->year)) goto bad;
 if(frame(&w,"TCON",t->genre)||frame(&w,"TCOM",t->composer)||(t->date&&*t->date&&extra(&w,"DATE",t->date))) goto bad;
 if(t->extra_count>32||(t->extra_count&&!t->extras)) goto bad;
 for(i=0;i<t->extra_count;i++) if(extra(&w,t->extras[i].name,t->extras[i].value)) goto bad;
 if(t->jpeg_bytes) {
  static const unsigned char prefix[]={0,'i','m','a','g','e','/','j','p','e','g',0,3,0};
  unsigned char header[10]={'A','P','I','C',0,0,0,0,0,0};
  if(!t->jpeg||t->jpeg_bytes<4||t->jpeg_bytes>524288||t->jpeg[0]!=255||t->jpeg[1]!=216||t->jpeg[t->jpeg_bytes-2]!=255||t->jpeg[t->jpeg_bytes-1]!=217) goto bad;
  be32(header+4,sizeof(prefix)+t->jpeg_bytes);
  if(block(&w,header,sizeof(header))||block(&w,prefix,sizeof(prefix))||block(&w,t->jpeg,t->jpeg_bytes)) goto bad;
 } else if(t->jpeg) goto bad;
 memcpy(out,"ID3\3\0\0",6);n=w.used-10;
 for(i=0;i<4;i++) out[9-i]=(unsigned char)((n>>(i*7))&127);
 *bytes=w.used;return 0;
bad: memset(out,0,cap);return -1;
}
