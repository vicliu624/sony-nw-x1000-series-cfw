#include "../../runtime/platform/player/host_hook.h"
#include "../../runtime/platform/player/source_service.h"
#include "../../runtime/platform/player/rpc_posix.h"
#include <assert.h>
#include <string.h>
static unsigned long thread=1;
static unsigned initializations,attachments;
static struct xw_stock_gui gui;
static unsigned service_ticks,invalidations,clock_failed;
unsigned long pthread_self(void){return thread;}
static int command(void *p,const struct xw_player_command *q,uint64_t n){(void)p;(void)q;(void)n;assert(0);return XW_PLAYER_PROTOCOL;}
static int revoke(void *p,uint64_t n){(void)p;(void)n;assert(0);return XW_PLAYER_PROTOCOL;}
static int close_adapter(void *p){(void)p;assert(0);return XW_PLAYER_PROTOCOL;}
int xw_source_service_init(struct xw_source_service *s,struct xw_stock_gui *g,struct xw_player_source_provider *out){
 assert(g==&gui&&!s->bound&&thread==1);initializations++;s->bound=1;
 struct xw_player_source_provider p={s,command,revoke,close_adapter};*out=p;return 0;
}
int xw_player_broker_attach_source(struct xw_player_broker *b,const struct xw_player_source_provider *p){
 assert(thread==1&&b->owner==1&&p->context&&p->command&&p->revoke&&p->close);attachments++;
 if(attachments==1)return XW_PLAYER_BUSY;b->source=*p;b->player.provider.commands|=1u<<XW_OP_PLAY_ITEM;return 0;
}
int hb_monotonic_millis(unsigned long long *out){if(clock_failed)return -1;*out=100;return 0;}
int xw_player_broker_bind(struct xw_player_broker *b,struct xw_player *p){b->backend=p;b->player.initialized=1;b->owner=thread;return 0;}
void xw_player_broker_tick(struct xw_player_broker *b,unsigned long long n){assert(b->player.initialized&&n==100);}
void xw_player_broker_invalidate(struct xw_player_broker *b,uint64_t n){assert(b->source.command&&clock_failed&&!n);invalidations++;}
int xw_player_rpc_server_open(struct xw_player_rpc_server *s,struct xw_player *p,const char *endpoint){assert(!strcmp(endpoint,XW_PLAYER_RPC_ENDPOINT));s->player=p;s->bound=1;return 0;}
int xw_player_rpc_server_tick(struct xw_player_rpc_server *s,unsigned long long n){assert(n==100&&s->bound);service_ticks++;assert(!!(s->player->provider.commands&(1u<<XW_OP_PLAY_ITEM))==(attachments>1));return 0;}
int xw_player_host_queue_attach(struct xw_player_broker *b){assert(b->player.initialized);return XW_PLAYER_UNAVAILABLE;}
int main(int argc,char **argv){
 static struct xw_player original;
 static struct xw_player_broker broker;
 if(argc>1){
  assert(!strcmp(argv[1],"--host"));original.initialized=1;gui.bound=1;gui.owner=1;xw_player_host_source_gui(&gui);
  xw_player_host_dispatch(&original);assert(service_ticks==1&&attachments==1&&initializations==1);
  xw_player_host_dispatch(&original);assert(service_ticks==2&&attachments==2&&initializations==1);
  xw_player_host_dispatch(&original);assert(service_ticks==3&&attachments==2&&initializations==1);
  clock_failed=1;xw_player_host_dispatch(&original);assert(service_ticks==3&&invalidations==1);return 0;
 }
 original.initialized=1;broker.backend=&original;broker.player.initialized=1;broker.owner=1;
 assert(xw_player_host_source_attach(0)==XW_PLAYER_CLOSED);
 assert(xw_player_host_source_attach(&broker)==XW_PLAYER_UNAVAILABLE&&!initializations);
 gui.bound=1;gui.owner=1;gui.busy=1;xw_player_host_source_gui(&gui);
 assert(xw_player_host_source_attach(&broker)==XW_PLAYER_UNAVAILABLE);gui.busy=0;
 thread=2;xw_player_host_source_gui(&gui);thread=1;assert(xw_player_host_source_attach(&broker)==XW_PLAYER_UNAVAILABLE);
 xw_player_host_source_gui(&gui);broker.owner=2;assert(xw_player_host_source_attach(&broker)==XW_PLAYER_BUSY);broker.owner=1;
 original.provider.commands=1u<<XW_OP_PLAY_ITEM;assert(xw_player_host_source_attach(&broker)==XW_PLAYER_UNSUPPORTED&&!initializations);original.provider.commands=0;
 assert(xw_player_host_source_attach(&broker)==XW_PLAYER_BUSY&&initializations==1&&attachments==1);
 assert(!xw_player_host_source_attach(&broker)&&initializations==1&&attachments==2);
 assert(broker.player.provider.commands&(1u<<XW_OP_PLAY_ITEM));
 assert(!xw_player_host_source_attach(&broker)&&initializations==1&&attachments==2);return 0;
}
