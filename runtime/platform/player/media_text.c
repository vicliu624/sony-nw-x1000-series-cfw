#include "media_text.h"
#include <string.h>
static int field_ok(unsigned field){return field==1||field==2||field==4;}
static unsigned encode(uint32_t c,unsigned char out[4]){
 if(c<0x80){out[0]=(unsigned char)c;return 1;}if(c<0x800){out[0]=0xc0|(c>>6);out[1]=0x80|(c&63);return 2;}
 if(c<0x10000){out[0]=0xe0|(c>>12);out[1]=0x80|((c>>6)&63);out[2]=0x80|(c&63);return 3;}
 out[0]=0xf0|(c>>18);out[1]=0x80|((c>>12)&63);out[2]=0x80|((c>>6)&63);out[3]=0x80|(c&63);return 4;
}
static void append(char *out,unsigned *used,unsigned *full,uint32_t code){unsigned char bytes[4];unsigned n=encode(code,bytes);if(!*full&&*used+n<XW_MEDIA_TEXT_BYTES){memcpy(out+*used,bytes,n);*used+=n;}else *full=1;}
int xw_media_text_utf16(const uint16_t *source,uint32_t count,char out[XW_MEDIA_TEXT_BYTES],uint32_t *flags,unsigned field){
 if(!out||!flags||!field_ok(field)||(!source&&count)||count>32768)return XW_PLAYER_INVALID;
 char staged[XW_MEDIA_TEXT_BYTES]={0};unsigned used=0,full=0;
 for(uint32_t i=0;i<count;i++){
  uint32_t c=source[i];if(!c)return XW_PLAYER_PROTOCOL;
  if(c>=0xd800&&c<=0xdbff){if(i+1>=count||source[i+1]<0xdc00||source[i+1]>0xdfff)return XW_PLAYER_PROTOCOL;c=0x10000+((c-0xd800)<<10)+(source[++i]-0xdc00);}
  else if(c>=0xdc00&&c<=0xdfff)return XW_PLAYER_PROTOCOL;
  append(staged,&used,&full,c);
 }
 memcpy(out,staged,sizeof staged);*flags|=field|(full?field<<8:0);return 0;
}
int xw_media_text_utf8(const unsigned char *source,uint32_t count,char out[XW_MEDIA_TEXT_BYTES],uint32_t *flags,unsigned field){
 if(!out||!flags||!field_ok(field)||(!source&&count)||count>65536)return XW_PLAYER_INVALID;
 char staged[XW_MEDIA_TEXT_BYTES]={0};unsigned used=0,full=0;
 for(uint32_t i=0;i<count;){unsigned c=source[i++],extra=0,minimum=0,code=c;if(!c)return XW_PLAYER_PROTOCOL;
  if(c>=0xc2&&c<=0xdf){extra=1;minimum=0x80;code=c&31;}else if(c>=0xe0&&c<=0xef){extra=2;minimum=0x800;code=c&15;}else if(c>=0xf0&&c<=0xf4){extra=3;minimum=0x10000;code=c&7;}else if(c>=0x80)return XW_PLAYER_PROTOCOL;
  while(extra--){if(i>=count||(source[i]&192)!=128)return XW_PLAYER_PROTOCOL;code=(code<<6)|(source[i++]&63);}
  if((minimum&&code<minimum)||code>0x10ffff||(code>=0xd800&&code<=0xdfff))return XW_PLAYER_PROTOCOL;
  append(staged,&used,&full,code);
 }
 memcpy(out,staged,sizeof staged);*flags|=field|(full?field<<8:0);return 0;
}
