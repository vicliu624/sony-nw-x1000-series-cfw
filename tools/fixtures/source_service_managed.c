/* Production managed ledger -> source service -> intent. Native validation,
 * GUI and submission are models supplied by the included source fixture. */
#define XW_MANAGED_SOURCE_FIXTURE
#define main source_unit_main
#include "source_service.c"
#undef main
#include "../../runtime/platform/player/managed.h"
#include <stdio.h>
static struct xw_source_service native_source;
static struct xw_player_source_provider source_provider;
static uint64_t time_now=100;
static int read_state(void *c,struct xw_player_snapshot *s){(void)c;(void)s;return XW_PLAYER_UNAVAILABLE;}
static int select_item(void *c,const struct xw_player_command *r){(void)c;return source_provider.command(source_provider.context,r,time_now++);}
static int close_source(void *c){(void)c;return source_provider.close(source_provider.context);}
int main(void){
 static struct xw_player backend;static struct xw_stock_gui gui;
 static struct xw_session_manager manager;static struct xw_managed_player a,b;
 struct xw_session_handle ah,bh;
 assert(!xw_source_service_init(&native_source,&gui,&source_provider));
 struct xw_player_provider p={XW_PLAYER_API,1u<<XW_OP_PLAY_ITEM,0,read_state,select_item,0,close_source};
 assert(!xw_player_bind(&backend,&p)&&!xw_sessions_init(&manager,17,7));
 assert(!xw_session_open(&manager,2,2,&ah)&&!xw_managed_player_bind(&a,&manager,ah,&backend));
 struct xw_player_command c={0};c.operation=XW_OP_PLAY_ITEM;c.expected_revision=0x1122334455667788ull;
 assert(!xw_local_media_id_format(1,1,&c.item));
 assert(xw_managed_player_command(&a,1,&c)==XW_PLAYER_BUSY&&native_source.generation==1&&!submissions);
 unsigned before=reads;validation=0;
 assert(xw_managed_player_command(&a,1,&c)==XW_PLAYER_BUSY&&reads==before&&!submissions);
 assert(xw_managed_player_command(&a,2,&c)==XW_PLAYER_ACCEPTED&&native_source.generation==1&&submissions==1);
 assert(native_source.revision==c.expected_revision);
 assert(xw_managed_player_command(&a,2,&c)==XW_PLAYER_ACCEPTED&&submissions==1);
 validation=XW_PLAYER_BUSY;
 assert(xw_managed_player_command(&a,3,&c)==XW_PLAYER_BUSY&&native_source.generation==2);
 before=reads;assert(xw_session_revoke(&manager,ah,XW_SESSION_HOME)==XW_SESSION_PENDING);
 validation=0;assert(xw_managed_player_command(&a,4,&c)==XW_PLAYER_UNAVAILABLE&&reads==before&&submissions==1);
 assert(!xw_managed_player_close(&a)&&backend.initialized&&native_source.bound);
 assert(!xw_session_open(&manager,2,2,&bh)&&!xw_managed_player_bind(&b,&manager,bh,&backend));
 assert(!xw_local_media_id_format(1,2,&c.item));
 assert(xw_managed_player_command(&b,1,&c)==XW_PLAYER_ACCEPTED&&native_source.generation==3&&submissions==2);
 assert(xw_managed_player_command(&a,4,&c)==XW_PLAYER_CLOSED&&submissions==2);
 available=0;assert(xw_managed_player_command(&b,2,&c)==XW_PLAYER_UNAVAILABLE&&submissions==2);available=1;
 assert(xw_managed_player_command(&b,3,&c)==XW_PLAYER_ACCEPTED&&submissions==3);
 validation=XW_PLAYER_BUSY;assert(xw_managed_player_command(&b,4,&c)==XW_PLAYER_BUSY);
 assert(!xw_managed_player_close(&b)&&backend.initialized);
 assert(xw_player_close(&backend)==XW_PLAYER_BUSY&&native_source.closing&&backend.initialized);
 drained=1;assert(!xw_player_close(&backend)&&!native_source.bound&&!backend.initialized);
 puts("MANAGED_SOURCE_SERVICE_PASS");return 0;
}
