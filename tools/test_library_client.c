#include "../runtime/apps/wireless-remote/library_client.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 struct wr_library_client client={0};struct xw_media_query query={0};query.limit=1;
 uint8_t key[32]={1},wire[WR_LIBRARY_REPLY_BYTES];
 assert(!wr_library_client_begin(&client,7,&query,1,wire,sizeof wire,key)&&client.pending&&client.serial==1);
 assert(wr_library_client_begin(&client,7,&query,2,wire,sizeof wire,key));
 struct wr_library_reply reply={0};reply.session=8;reply.request=1;reply.page=(struct xw_media_page){11,0,1,4,1};strcpy(reply.item.id.value,"track");
 assert(!wr_library_reply_encode(wire,sizeof wire,&reply,key));struct wr_library_client before=client;
 assert(wr_library_client_accept(&client,wire,sizeof wire,key)&&!memcmp(&before,&client,sizeof client));
 reply.session=7;assert(!wr_library_reply_encode(wire,sizeof wire,&reply,key));assert(!wr_library_client_accept(&client,wire,sizeof wire,key)&&client.have&&!client.pending);
 query.offset=1;query.expected_revision=11;assert(!wr_library_client_begin(&client,7,&query,4,wire,sizeof wire,key)&&client.serial==2);
 reply.request=1;assert(!wr_library_reply_encode(wire,sizeof wire,&reply,key));assert(wr_library_client_accept(&client,wire,sizeof wire,key));
 reply.request=2;reply.page=(struct xw_media_page){12,1,1,4,2};assert(!wr_library_reply_encode(wire,sizeof wire,&reply,key));assert(wr_library_client_accept(&client,wire,sizeof wire,key));
 assert(!wr_library_client_tick(&client,5003));assert(wr_library_client_tick(&client,5004)&&!client.pending&&!client.have);
 reply.page.revision=11;assert(!wr_library_reply_encode(wire,sizeof wire,&reply,key));assert(wr_library_client_accept(&client,wire,sizeof wire,key));
 assert(!wr_library_client_begin(&client,7,&query,4000,wire,sizeof wire,key)&&client.serial==3);
 memset(&reply,0,sizeof reply);reply.session=7;reply.request=3;reply.result=XW_PLAYER_STALE;assert(!wr_library_reply_encode(wire,sizeof wire,&reply,key));assert(!wr_library_client_accept(&client,wire,sizeof wire,key)&&client.result==XW_PLAYER_STALE&&!client.have);
 assert(!wr_library_client_begin(&client,8,&query,5000,wire,sizeof wire,key)&&client.serial==1&&client.session==8);
 assert(wr_library_client_tick(&client,4999));client.serial=UINT32_MAX;before=client;assert(wr_library_client_begin(&client,8,&query,6000,wire,sizeof wire,key)&&!memcmp(&before,&client,sizeof client));
 wr_library_client_clear(&client);assert(!client.session&&!client.pending&&!client.have);puts("REMOTE_LIBRARY_CLIENT_CORRELATION_PASS");return 0;
}
