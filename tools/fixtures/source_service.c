#include "../../runtime/platform/player/source_service.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <string.h>
static unsigned long thread=1;
static unsigned available=1,drained,submissions,stops,reads;
static int validation=XW_PLAYER_BUSY;
unsigned long pthread_self(void){return thread;}
int xw_audio_check_async_init(struct xw_audio_check_async *s){s->worker.initialized=1;s->worker.owner=thread;return 0;}
int xw_audio_check_async_observe(struct xw_audio_check_async *s,const struct xw_media_id *id,uint64_t generation,uint64_t now,struct xw_stock_audio_identity *out){
 (void)s;(void)now;if(!id)return XW_PLAYER_UNAVAILABLE;assert(generation);reads++;if(validation)return validation;
 memset(out,0,sizeof *out);out->id=*id;out->media_type=1;return 0;
}
int xw_stock_media_source_ready(void){assert(thread==1);return available;}
int xw_stock_gui_read(struct xw_stock_gui *g,struct xw_stock_gui_view *out){assert(g&&thread==1);memset(out,0,sizeof *out);out->active=1;out->mode=1;out->state=5;return 0;}
int xw_stock_source_submit(struct xw_stock_gui *g,const struct xw_media_id *id,struct xw_stock_source_result *out){assert(g&&id->value[0]&&thread==1);submissions++;out->attempted=out->moved=1;out->ticket=77;return XW_PLAYER_ACCEPTED;}
#ifndef XW_MANAGED_SOURCE_FIXTURE
int xw_player_snapshot(struct xw_player *p,struct xw_player_snapshot *out){(void)p;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
#endif
int xw_metadata_async_stop(struct xw_metadata_async *s){assert(s->initialized&&thread==1);stops++;return XW_PLAYER_ACCEPTED;}
int xw_metadata_async_drained(struct xw_metadata_async *s){assert(s->initialized);return drained;}
int xw_metadata_async_destroy(struct xw_metadata_async *s){assert(s->initialized&&drained);memset(s,0,sizeof *s);return 0;}
int main(void){
 static struct xw_source_service service;
 static struct xw_stock_gui gui;
 struct xw_player_source_provider provider;
 struct xw_player_command request={0};request.operation=XW_OP_PLAY_ITEM;assert(!xw_local_media_id_format(1,1,&request.item));
 assert(!xw_source_service_init(&service,&gui,&provider));assert(xw_source_service_init(&service,&gui,&provider)==XW_PLAYER_BUSY);
 assert(provider.command(provider.context,&request,100)==XW_PLAYER_BUSY&&service.pending&&service.generation==1&&!submissions);
 assert(provider.command(provider.context,&request,101)==XW_PLAYER_BUSY&&service.generation==1);
 assert(!xw_local_media_id_format(1,2,&request.item));assert(provider.command(provider.context,&request,102)==XW_PLAYER_BUSY&&service.generation==2);
 validation=0;assert(provider.command(provider.context,&request,103)==XW_PLAYER_ACCEPTED&&!service.pending&&service.generation==2&&submissions==1);
 /* A new explicit command after admission is a new intent, not a cached poll. */
 assert(provider.command(provider.context,&request,104)==XW_PLAYER_ACCEPTED&&service.generation==3&&submissions==2);
 validation=XW_PLAYER_BUSY;request.expected_revision=7;assert(provider.command(provider.context,&request,105)==XW_PLAYER_BUSY&&service.generation==4);
 unsigned before=reads;thread=2;assert(provider.command(provider.context,&request,106)==XW_PLAYER_BUSY&&reads==before&&service.generation==4);thread=1;
 assert(!provider.revoke(provider.context,106)&&!service.pending);
 validation=0;assert(provider.command(provider.context,&request,107)==XW_PLAYER_ACCEPTED&&service.generation==5&&submissions==3);
 available=0;assert(provider.command(provider.context,&request,108)==XW_PLAYER_UNAVAILABLE&&!service.pending&&submissions==3);available=1;
 assert(provider.command(provider.context,&request,109)==XW_PLAYER_ACCEPTED&&service.generation==7&&submissions==4);
 service.generation=UINT64_MAX;assert(provider.command(provider.context,&request,110)==XW_PLAYER_UNAVAILABLE&&submissions==4);
 assert(provider.close(provider.context)==XW_PLAYER_BUSY&&service.closing&&stops==1);
 before=reads;assert(provider.command(provider.context,&request,111)==XW_PLAYER_CLOSED&&reads==before);
 drained=1;assert(!provider.close(provider.context)&&stops==2&&!service.bound);
 assert(provider.command(provider.context,&request,112)==XW_PLAYER_CLOSED);return 0;
}
