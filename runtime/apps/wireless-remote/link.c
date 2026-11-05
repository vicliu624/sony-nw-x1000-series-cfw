#include "link.h"
#include <string.h>
static uint32_t get(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static int text(const char *s,size_t n,int ascii){
 size_t i=0;while(i<n){unsigned c=(unsigned char)s[i++];if(!c){while(i<n)if(s[i++])return 0;return 1;}
 if(c<32||c==127)return 0;if(c<128)continue;if(ascii)return 0;
 unsigned count,min,value;if(c>=0xc2&&c<=0xdf){count=1;min=128;value=c&31;}
 else if(c>=0xe0&&c<=0xef){count=2;min=2048;value=c&15;}
 else if(c>=0xf0&&c<=0xf4){count=3;min=65536;value=c&7;}else return 0;
 if(i+count>n)return 0;while(count--){c=(unsigned char)s[i++];if((c&192)!=128)return 0;value=(value<<6)|(c&63);}
 if(value<min||value>0x10ffff||(value>=0xd800&&value<=0xdfff))return 0;
 }return 0;
}
static int valid(const struct wr_status *s){
 return s&&s->session&&s->sequence&&!(s->valid&~63u)&&!(s->commands&~127u)&&s->state<=4&&
 !(s->metadata_flags&~1799u)&&(!(s->valid&32u)||(s->minimum>=0&&s->maximum>=s->minimum&&s->volume>=s->minimum&&s->volume<=s->maximum))&&
 text(s->id,sizeof s->id,1)&&text(s->title,sizeof s->title,0)&&text(s->artist,sizeof s->artist,0)&&text(s->album,sizeof s->album,0);
}
int wr_status_encode(void *output,size_t bytes,const struct wr_status *s){
 if(!output||bytes<WR_STATUS_BYTES||!valid(s))return -1;
 uint8_t *p=output;memset(p,0,WR_STATUS_BYTES);memcpy(p,"WRS1",4);
 put(p+4,(uint32_t)s->session);put(p+8,(uint32_t)(s->session>>32));
 put(p+12,s->sequence);put(p+16,s->valid);put(p+20,s->commands);put(p+24,s->state);
 put(p+28,s->metadata_flags);put(p+32,(uint32_t)s->volume);put(p+36,(uint32_t)s->minimum);put(p+40,(uint32_t)s->maximum);
 memcpy(p+44,s->id,65);memcpy(p+109,s->title,256);memcpy(p+365,s->artist,256);memcpy(p+621,s->album,256);
 return 0;
}
int wr_status_decode(struct wr_status *out,const void *input,size_t bytes){
 if(!out||!input||bytes!=WR_STATUS_BYTES)return -1;
 const uint8_t *p=input;if(memcmp(p,"WRS1",4))return -1;
 struct wr_status s;memset(&s,0,sizeof s);s.session=get(p+4)|(uint64_t)get(p+8)<<32;
 s.sequence=get(p+12);s.valid=get(p+16);s.commands=get(p+20);s.state=get(p+24);s.metadata_flags=get(p+28);
 s.volume=(int32_t)get(p+32);s.minimum=(int32_t)get(p+36);s.maximum=(int32_t)get(p+40);
 memcpy(s.id,p+44,65);memcpy(s.title,p+109,256);memcpy(s.artist,p+365,256);memcpy(s.album,p+621,256);
 if(!valid(&s))return -1;*out=s;return 0;
}
