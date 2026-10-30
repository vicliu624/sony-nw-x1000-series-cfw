#include "../../runtime/platform/player/media_text.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 char out[256],prior[256];uint32_t flags=0;
 uint16_t text[]={65,0x732b,0xd83d,0xde3a};
 assert(!xw_media_text_utf16(text,4,out,&flags,1)&&!strcmp(out,"A猫😺")&&flags==1);
 flags=0;assert(!xw_media_text_utf8((const unsigned char *)"A猫😺",8,out,&flags,2)&&!strcmp(out,"A猫😺")&&flags==2);
 uint16_t long_text[101];for(unsigned i=0;i<100;i++)long_text[i]=0x732b;
 flags=4;assert(!xw_media_text_utf16(long_text,100,out,&flags,1)&&strlen(out)==255&&flags==(4|1|256));
 memcpy(prior,out,sizeof prior);uint32_t old=flags;
 long_text[100]=0xd800;assert(xw_media_text_utf16(long_text,101,out,&flags,1)==XW_PLAYER_PROTOCOL&&!memcmp(prior,out,sizeof prior)&&flags==old);
 uint16_t low[]={0xdc00},embedded[]={65,0,66};assert(xw_media_text_utf16(low,1,out,&flags,2)==XW_PLAYER_PROTOCOL);assert(xw_media_text_utf16(embedded,3,out,&flags,2)==XW_PLAYER_PROTOCOL);
 static const unsigned char bad[][4]={{0xc0,0x80,0,0},{0xed,0xa0,0x80,0},{0xf4,0x90,0x80,0x80},{65,0,66,0}};unsigned lengths[]={2,3,4,3};
 for(unsigned i=0;i<4;i++)assert(xw_media_text_utf8(bad[i],lengths[i],out,&flags,4)==XW_PLAYER_PROTOCOL&&!memcmp(prior,out,sizeof prior)&&flags==old);
 assert(xw_media_text_utf16(0,1,out,&flags,1)==XW_PLAYER_INVALID);assert(xw_media_text_utf8(0,1,out,&flags,1)==XW_PLAYER_INVALID);assert(xw_media_text_utf8((const unsigned char *)"x",1,out,&flags,8)==XW_PLAYER_INVALID);
 flags=0;assert(!xw_media_text_utf16(0,0,out,&flags,4)&&!out[0]&&flags==4);
 flags=0;assert(!xw_media_text_utf8(0,0,out,&flags,1)&&!out[0]&&flags==1);
 puts("Media text: UTF-16 units, BMP/surrogates, UTF-8, whole-codepoint bounds, late malformed data and atomic refusal passed");return 0;
}
