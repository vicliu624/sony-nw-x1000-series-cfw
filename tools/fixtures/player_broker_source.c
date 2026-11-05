#include "../../runtime/platform/player/player_broker.h"
#include <assert.h>
#include <string.h>
static unsigned long thread=1;
static unsigned available=1,clock_failed,source_commands,revokes,closes,backend_commands,backend_closes,revoke_busy;
static uint64_t revision=7;
static unsigned long long now=100;
static int source_result=XW_PLAYER_ACCEPTED;
static int backend_fault;
unsigned long pthread_self(void){return thread;}
int hb_monotonic_millis(unsigned long long *out){if(clock_failed)return -1;*out=now;return 0;}
int xw_stock_media_source_ready(void){assert(thread==1);return available;}
int xw_metadata_async_init(struct xw_metadata_async *s){(void)s;return XW_PLAYER_UNAVAILABLE;}
int xw_children_async_init(struct xw_children_async *s){(void)s;return XW_PLAYER_UNAVAILABLE;}
int xw_metadata_async_observe(struct xw_metadata_async *s,const struct xw_media_id *id,uint64_t r,unsigned long long n,struct xw_media_item *out){(void)s;(void)id;(void)r;(void)n;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_children_async_observe(struct xw_children_async *s,const struct xw_stock_children_query *q,uint64_t r,unsigned long long n,struct xw_stock_children_page *out){(void)s;(void)q;(void)r;(void)n;(void)out;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_metadata_async_stop(struct xw_metadata_async *s){(void)s;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_metadata_async_drained(struct xw_metadata_async *s){(void)s;assert(0);return 0;}
int xw_metadata_async_destroy(struct xw_metadata_async *s){(void)s;assert(0);return XW_PLAYER_PROTOCOL;}
static int snapshot(void *context,struct xw_player_snapshot *out){(void)context;if(backend_fault)return backend_fault;memset(out,0,sizeof *out);out->library_revision=revision;return 0;}
static int command(void *context,const struct xw_player_command *c){(void)context;assert(c->operation==XW_OP_NEXT);backend_commands++;return XW_PLAYER_ACCEPTED;}
static int close_backend(void *context){(void)context;backend_closes++;return 0;}
static int source_command(void *context,const struct xw_player_command *c,uint64_t clock){assert(context==&source_commands&&c->operation==XW_OP_PLAY_ITEM&&clock==now);source_commands++;return source_result;}
static int source_revoke(void *context,uint64_t clock){assert(context==&source_commands&&clock==(clock_failed?0:now));revokes++;if(revoke_busy){revoke_busy=0;return XW_PLAYER_BUSY;}return 0;}
static int source_close(void *context){assert(context==&source_commands);return ++closes==1?XW_PLAYER_BUSY:0;}
int main(void){
 static struct xw_player original;
 static struct xw_player_broker broker;
 struct xw_player_provider p={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_backend};
 assert(!xw_player_bind(&original,&p)&&!xw_player_broker_bind(&broker,&original));
 struct xw_player_command request={0};request.operation=XW_OP_PLAY_ITEM;memcpy(request.item.value,"song:1",7);
 assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNSUPPORTED);
 struct xw_player_source_provider source={&source_commands,source_command,source_revoke,source_close};
 thread=2;assert(xw_player_broker_attach_source(&broker,&source)==XW_PLAYER_BUSY);thread=1;
 assert(!xw_player_broker_attach_source(&broker,&source));assert(xw_player_broker_attach_source(&broker,&source)==XW_PLAYER_BUSY);
 request.expected_revision=8;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_STALE&&!source_commands);
 request.expected_revision=7;revision=0;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_STALE&&!source_commands);revision=7;
 thread=2;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_BUSY&&!source_commands);thread=1;
 assert(xw_player_command(&broker.player,&request)==XW_PLAYER_ACCEPTED&&source_commands==1);
 source_result=XW_PLAYER_BUSY;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_BUSY&&source_commands==2);
 source_result=XW_PLAYER_UNCERTAIN;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNCERTAIN&&source_commands==3);
 memcpy(request.container.value,"list:1",7);assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNSUPPORTED&&source_commands==3);request.container.value[0]=0;
 clock_failed=1;revoke_busy=1;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNAVAILABLE&&broker.source_revoke_pending&&source_commands==3);
 clock_failed=0;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNCERTAIN&&!broker.source_revoke_pending&&source_commands==4&&revokes==2);
 available=0;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNAVAILABLE&&source_commands==4);
 xw_player_broker_tick(&broker,now);assert(revokes==4);thread=2;xw_player_broker_tick(&broker,now);thread=1;assert(revokes==4);available=1;
 xw_player_broker_invalidate(&broker,now);assert(revokes==5);thread=2;xw_player_broker_invalidate(&broker,now);thread=1;assert(revokes==5);
 request.operation=XW_OP_NEXT;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_ACCEPTED&&backend_commands==1&&source_commands==4);
 struct xw_player_snapshot observed,prior;uint32_t changes;
 assert(!xw_player_poll(&broker.player,&observed,&changes));prior=observed;changes=0x5a5a5a5a;
 backend_fault=XW_PLAYER_UNAVAILABLE;revoke_busy=1;
 assert(xw_player_poll(&broker.player,&observed,&changes)==XW_PLAYER_UNAVAILABLE&&!memcmp(&observed,&prior,sizeof observed)&&changes==0x5a5a5a5a&&revokes==6&&broker.source_revoke_pending&&source_commands==4);
 backend_fault=XW_PLAYER_BUSY;
 assert(xw_player_poll(&broker.player,&observed,&changes)==XW_PLAYER_BUSY&&revokes==6&&source_commands==4);
 backend_fault=0;assert(!xw_player_poll(&broker.player,&observed,&changes)&&(changes&XW_PC_AVAILABLE)&&source_commands==4);
 request.operation=XW_OP_PLAY_ITEM;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_UNCERTAIN&&source_commands==5&&!broker.source_revoke_pending&&revokes==7);
 backend_fault=XW_PLAYER_CLOSED;assert(xw_player_command(&broker.player,&request)==XW_PLAYER_CLOSED&&source_commands==5&&revokes==8);backend_fault=0;
 assert(xw_player_close(&broker.player)==XW_PLAYER_BUSY&&broker.player.initialized&&original.initialized&&!backend_closes);
 assert(!xw_player_close(&broker.player)&&closes==2&&!backend_closes&&original.initialized);
 assert(!xw_player_close(&original)&&backend_closes==1);return 0;
}
