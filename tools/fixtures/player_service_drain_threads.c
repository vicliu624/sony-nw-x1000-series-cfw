/* Production broker/reader/drain, modeled Moma reads held in actual threads. */
#define main broker_unit_main
#define xw_stock_media_fetch base_media_fetch
#define xw_stock_media_children base_media_children
#include "player_broker.c"
#undef xw_stock_media_fetch
#undef xw_stock_media_children
#undef main
#include "../../runtime/platform/player/service_drain.h"
#include "../../runtime/platform/player/managed_host.h"
#include "../../runtime/platform/services/descriptor.h"
#include <sys/socket.h>
#include <unistd.h>
static union xw_pthread_storage gate_mutex,gate_condition;
static unsigned entered,allow_finish;
static struct xw_managed_host host;
static unsigned native_pending=1,notifications;
static void *wrong_prepare_owner(void *context){(void)context;assert(xw_managed_host_tick(&host,now)==XW_PLAYER_BUSY);return 0;}
static int registered(void *context,uint64_t epoch){(void)context;assert(epoch==1);return native_pending!=0;}
static int notify(void *context,uint64_t epoch){
 (void)context;assert(epoch==1&&!broker.player.initialized&&original.initialized);
 assert(xw_managed_host_tick(&host,now)==XW_PLAYER_BUSY);
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);pthread_mutex_unlock((void *)&counters);
 notifications++;native_pending=0;return 0;
}
static void wait_gate(void){
 pthread_mutex_lock((void *)&gate_mutex);entered++;pthread_cond_broadcast((void *)&gate_condition);
 while(!allow_finish)pthread_cond_wait((void *)&gate_condition,(void *)&gate_mutex);
 pthread_mutex_unlock((void *)&gate_mutex);
}
int xw_stock_media_fetch(struct xw_stock_media *s,const struct xw_media_id *id,struct xw_media_item *out){wait_gate();return base_media_fetch(s,id,out);}
int xw_stock_media_children(struct xw_stock_media *s,const struct xw_stock_children_query *q,struct xw_stock_children_page *out){wait_gate();return base_media_children(s,q,out);}
#ifdef HB_MANAGER_DRAIN_FIXTURE
int xw_fixture_player_drain(void){
#else
int main(void){
#endif
 assert(!pthread_mutex_init((void *)&counters,0)&&!pthread_mutex_init((void *)&gate_mutex,0)&&!pthread_cond_init((void *)&gate_condition,0));
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_backend};
 assert(!xw_player_bind(&original,&provider)&&!xw_player_broker_bind(&broker,&original));
 static struct xw_player_session_offer offer;struct xw_player_session_offer *offers[]={&offer};
 assert(!xw_managed_host_init(&host,&broker,31,7,offers,1));
 int delivery[2],client;struct xw_descriptor_offer identity;
 assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 assert(!xw_managed_host_offer(&host,delivery[0],5,5,now));
 assert(!xw_service_descriptor_receive(delivery[1],&client,&identity));
 struct xw_rpc_request hello={0};hello.kind=XW_RPC_HELLO;hello.serial=1;
 unsigned char frame[XW_RPC_REQUEST_MAX];size_t size;
 assert(!xw_rpc_encode_request(&hello,frame,sizeof frame,&size)&&write(client,frame,size)==(ssize_t)size);
 assert(!xw_managed_host_tick(&host,now)&&offer.channel.hello);
 struct xw_player_snapshot observed;assert(!xw_managed_player_snapshot(&offer.player,&observed));
 struct xw_media_query query={0};query.limit=1;static struct xw_media_item rows[16];struct xw_media_page page;
 assert(xw_managed_player_browse(&offer.player,&query,rows,16,&page)==XW_PLAYER_BUSY);
 unsigned ready=0;
 for(unsigned i=0;i<2000;i++){pthread_mutex_lock((void *)&gate_mutex);ready=entered;pthread_mutex_unlock((void *)&gate_mutex);if(ready==2)break;poll(0,0,1);}
 assert(ready==2);
 assert(xw_managed_host_stop(&host,XW_SESSION_USB)==XW_PLAYER_BUSY);
 assert(xw_managed_host_tick(&host,now)==XW_PLAYER_BUSY&&host.drain.phase==XW_DRAIN_BACKEND&&!notifications);
 /* Exit arrives while ordinary SDK drain is already in progress. */
 assert(xw_managed_host_prepare(&host,XW_SESSION_USB,1,0,registered,notify)==XW_PLAYER_BUSY);
 assert(xw_managed_host_prepare(&host,XW_SESSION_USB,1,0,registered,notify)==XW_PLAYER_BUSY&&!notifications);
 assert(xw_managed_host_offer(&host,delivery[0],1,1,now)==XW_PLAYER_CLOSED);
 pthread_t other;assert(!pthread_create(&other,0,wrong_prepare_owner,0));assert(!pthread_join(other,0));
 assert(xw_managed_host_tick(&host,now)==XW_PLAYER_BUSY&&host.drain.phase==XW_DRAIN_BACKEND&&!notifications);
 assert(!xw_sessions_drained(&host.manager)&&broker.player.initialized&&original.initialized&&!backend_closed);
 pthread_mutex_lock((void *)&counters);assert(opened==2&&live==2&&!closed);pthread_mutex_unlock((void *)&counters);
 pthread_mutex_lock((void *)&gate_mutex);allow_finish=1;pthread_cond_broadcast((void *)&gate_condition);pthread_mutex_unlock((void *)&gate_mutex);
 int rc=XW_PLAYER_BUSY;
 for(unsigned i=0;i<2000&&rc==XW_PLAYER_BUSY;i++){rc=xw_managed_host_tick(&host,now);if(rc==XW_PLAYER_BUSY)poll(0,0,1);}
 assert(!rc&&host.drain.phase==XW_DRAIN_DONE&&host.phase==XW_HOST_STOPPED&&!broker.player.initialized&&original.initialized&&!backend_closed);
 assert(notifications==1&&!xw_managed_host_tick(&host,now)&&notifications==1);
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);pthread_mutex_unlock((void *)&counters);
 assert(!xw_player_close(&original)&&backend_closed==1);
 close(client);close(delivery[0]);close(delivery[1]);
 assert(!pthread_cond_destroy((void *)&gate_condition)&&!pthread_mutex_destroy((void *)&gate_mutex)&&!pthread_mutex_destroy((void *)&counters));
 puts("PLAYER_SERVICE_DRAIN_THREADS_PASS");return 0;
}
