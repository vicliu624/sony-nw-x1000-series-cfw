#include "../../runtime/platform/player/stock_engine_control.h"
struct xw_stock_engine_control engine;
unsigned long test_thread=7;
unsigned test_primary=2,test_error,test_substate,test_track=1;
unsigned test_replace_session;
unsigned long pthread_self(void){return test_thread;}
struct image_info {const char *name;void *base;const char *symbol;void *address;};
int dladdr(const void *address,struct image_info *out){(void)address;out->name="SpiderApp";out->base=(void *)0x8000;out->symbol=0;out->address=0;return 1;}
int xw_stock_info_bind(struct xw_stock_info *s){s->bound=1;s->owner=test_thread;return 0;}
int xw_stock_info_read(struct xw_stock_info *s,struct xw_stock_info_view *out){(void)s;out->primary=test_primary;out->error=test_error;out->substate=test_substate;out->track_present=out->track_id_valid=test_track;if(test_replace_session){volatile unsigned *controller=*(volatile unsigned *volatile *)0x6922d8u;controller[test_replace_session-1]++;}return 0;}
int xw_stock_info_unbind(struct xw_stock_info *s){s->bound=0;return 0;}
void *memset(void *p,int v,unsigned n){unsigned char *b=p;while(n--)*b++=(unsigned char)v;return p;}
void _start(void){for(;;){}}
#ifdef XW_ENGINE_PROVIDER_FIXTURE
#include "../../runtime/platform/player/engine_provider.h"
static struct xw_player base_player,adapter_player;
static struct xw_engine_provider adapter;
unsigned test_base_commands,test_base_closes,test_base_snapshots,test_base_browses;
static struct xw_player_snapshot sample;
void *memcpy(void *p,const void *s,unsigned n){unsigned char *a=p;const unsigned char *b=s;while(n--)*a++=*b++;return p;}
int strcmp(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}
static int base_snapshot(void *c,struct xw_player_snapshot *out){(void)c;test_base_snapshots++;memset(out,0,sizeof *out);out->valid=XW_PF_VOLUME;out->volume=10;out->volume_max=30;return 0;}
static int base_command(void *c,const struct xw_player_command *op){(void)c;(void)op;test_base_commands++;return XW_PLAYER_ACCEPTED;}
static int base_browse(void *c,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){(void)c;(void)items;test_base_browses++;memset(page,0,sizeof *page);page->offset=q->offset;return 0;}
static int base_close(void *c){(void)c;test_base_closes++;return 0;}
int test_provider_bind(void){
 struct xw_player_provider p={XW_PLAYER_API,1u<<XW_OP_STEP_VOLUME,0,base_snapshot,base_command,base_browse,base_close};
 int rc=xw_player_bind(&base_player,&p);if(rc)return rc;
 return xw_engine_player_bind(&adapter_player,&adapter,&base_player);
}
int test_provider_command(unsigned op){struct xw_player_command c={0};c.operation=op;return xw_player_command(&adapter_player,&c);}
int test_provider_volume(void){struct xw_player_command c={0};c.operation=XW_OP_STEP_VOLUME;c.value=1;return xw_player_command(&adapter_player,&c);}
int test_provider_invalid(void){struct xw_player_command c={0};c.operation=XW_OP_NEXT;c.value=1;return xw_player_command(&adapter_player,&c);}
int test_provider_browse(void){static struct xw_media_item item;struct xw_media_query q={0};struct xw_media_page page;q.limit=1;return xw_media_browse(&adapter_player,&q,&item,1,&page);}
int test_provider_snapshot(void){return xw_player_snapshot(&adapter_player,&sample);}
int test_provider_close(void){return xw_player_close(&adapter_player);}
int test_provider_base_alive(void){return base_player.initialized;}
#endif
