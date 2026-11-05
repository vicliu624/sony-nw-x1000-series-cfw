#include "../runtime/apps/wireless-remote/library_wire.h"
#include "../runtime/platform/espnow/xnow_client.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 uint8_t key[32]={1},wire[WR_LIBRARY_REPLY_BYTES];assert(sizeof wire<=XNOW_CLIENT_PAYLOAD_MAX);
 struct wr_library_request q={0},decoded={0};q.session=17;q.request=2;q.query.limit=1;q.query.expected_revision=99;
 assert(!wr_library_request_encode(wire,sizeof wire,&q,key));assert(!wr_library_request_decode(&decoded,wire,WR_LIBRARY_REQUEST_BYTES,key));assert(decoded.query.expected_revision==99&&decoded.query.limit==1);
 struct wr_library_request saved=decoded;wire[97]=1;assert(!wr_auth_tag(wire+104,wire,104,key));assert(wr_library_request_decode(&decoded,wire,120,key)&&!memcmp(&saved,&decoded,sizeof saved));
 q.query.view=XW_MEDIA_PLAYLIST_TRACKS;assert(wr_library_request_encode(wire,sizeof wire,&q,key));strcpy(q.query.container.value,"playlist-7");assert(!wr_library_request_encode(wire,sizeof wire,&q,key));
 struct wr_library_reply r={0},result={0};r.session=17;r.request=2;r.page.revision=99;r.page.count=1;r.page.total=4;r.page.next_offset=1;
 strcpy(r.item.id.value,"track-8");strcpy(r.item.title,"Music \xe9\x9f\xb3\xe6\xa8\x82");strcpy(r.item.artist,"Artist");r.item.flags=XW_MEDIA_TITLE_PRESENT|XW_MEDIA_ARTIST_PRESENT;r.item.duration_ms=123456;
 memset(r.item.title+strlen(r.item.title)+1,0xa5,sizeof r.item.title-strlen(r.item.title)-1);
 assert(!wr_library_reply_encode(wire,sizeof wire,&r,key));assert(!wr_library_reply_decode(&result,wire,sizeof wire,key));assert(!strcmp(r.item.title,result.item.title)&&result.item.duration_ms==123456&&result.page.total==4);
 struct wr_library_reply previous=result;wire[60]^=1;assert(wr_library_reply_decode(&result,wire,sizeof wire,key)&&!memcmp(&previous,&result,sizeof result));
 r.item.title[0]=(char)0xc0;assert(wr_library_reply_encode(wire,sizeof wire,&r,key));
 memset(&r,0,sizeof r);r.session=17;r.request=3;r.result=XW_PLAYER_UNSUPPORTED;
 assert(!wr_library_reply_encode(wire,sizeof wire,&r,key));assert(!wr_library_reply_decode(&result,wire,sizeof wire,key)&&result.result==XW_PLAYER_UNSUPPORTED&&!result.page.count);
 wire[44]=1;assert(!wr_auth_tag(wire+sizeof wire-16,wire,sizeof wire-16,key));assert(wr_library_reply_decode(&result,wire,sizeof wire,key));
 puts("REMOTE_LIBRARY_WIRE_PASS");return 0;
}
