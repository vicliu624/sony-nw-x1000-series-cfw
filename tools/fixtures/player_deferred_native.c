/* Real drain/session/client core; broker worker readiness and native identity
 * are models. The continuation executes the original prepare instructions. */
#include "stock_info_host.c"
#include "../../runtime/platform/player/deferred_prepare.h"
int strcmp(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}
static struct xw_player original;
static struct xw_player_broker broker;
static struct xw_session_manager manager;
static struct xw_player_service_drain drain;
static struct xw_deferred_prepare prepare;
static uint32_t root_address;
unsigned test_readers=2,test_forwards,test_native_output,test_context_valid=1;
static int snapshot(void *c,struct xw_player_snapshot *s){(void)c;(void)s;return XW_PLAYER_UNAVAILABLE;}
static int close_original(void *c){(void)c;return XW_PLAYER_IO;}
static int close_broker(void *c){struct xw_player_broker *b=c;if(test_readers)return XW_PLAYER_BUSY;b->backend=0;return 0;}
int xw_managed_player_close(struct xw_managed_player *p){(void)p;return XW_PLAYER_CLOSED;}
int xw_managed_channel_close(struct xw_managed_channel *c){(void)c;return XW_PLAYER_CLOSED;}
static int valid(void *c,uint64_t epoch){return c==&root_address&&epoch==1&&root_address&&test_context_valid;}
static int resume(void *c,uint64_t epoch){
 if(!valid(c,epoch))return XW_PLAYER_UNAVAILABLE;
 uint32_t output=0;test_forwards++;
 int rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x112fcu)(root_address,3,&output);
 test_native_output=output;return rc;
}
int test_init(void){
 struct xw_player_provider o={XW_PLAYER_API,0,0,snapshot,0,0,close_original};
 struct xw_player_provider b={XW_PLAYER_API,0,&broker,snapshot,0,0,close_broker};
 int rc=xw_player_bind(&original,&o);if(rc)return rc;
 broker.backend=&original;rc=xw_player_bind(&broker.player,&b);if(rc)return rc;
 rc=xw_sessions_init(&manager,51,7);if(rc)return rc;
 return xw_player_service_drain_init(&drain,&manager,&broker,0,0);
}
int test_defer(uint32_t root,uint32_t command){
 if(command!=3)return XW_PLAYER_INVALID;
 if(root_address&&root_address!=root)return XW_PLAYER_BUSY;
 root_address=root;
 return xw_deferred_prepare_begin(&prepare,&drain,XW_SESSION_CLIENT_CLOSE,1,&root_address,valid,resume);
}
int test_step(void){return xw_deferred_prepare_step(&prepare);}
int test_accepting(void){return manager.accepting;}
