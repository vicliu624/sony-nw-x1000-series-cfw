/* Real managed/source/intent/validation workers. GUI and native Moma modeled. */
#define XW_ASYNC_MANAGED_FIXTURE
#define XW_TEST_PTHREAD_ATOMICS
#define main source_async_unit_main
#include "source_intent_async.c"
#undef main
#include "../../runtime/platform/player/source_service.h"
#include "../../runtime/platform/player/managed.h"
#include <stdio.h>
static struct xw_source_service service;
static struct xw_player_source_provider source;
static int state_read(void *c,struct xw_player_snapshot *s){(void)c;(void)s;return XW_PLAYER_UNAVAILABLE;}
static int source_command(void *c,const struct xw_player_command *r){(void)c;return source.command(source.context,r,now++);}
static int source_close(void *c){(void)c;return source.close(source.context);}
static int explicit_poll(struct xw_managed_player *p,uint64_t *id,const struct xw_player_command *c){
 for(unsigned i=0;i<5000;i++){
  int rc=xw_managed_player_command(p,++*id,c);
  if(rc!=XW_PLAYER_BUSY&&rc!=XW_PLAYER_UNAVAILABLE)return rc;
  usleep(1000);
 }
 assert(0);return XW_PLAYER_IO;
}
int main(void){
 assert(!pthread_mutex_init((void *)&atomic_guard,0));owner=pthread_self();
 assert(!xw_source_service_init(&service,&gui,&source));tested_intent=&service.intent;
 static struct xw_player backend;static struct xw_managed_player a,b;static struct xw_session_manager manager;
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_PLAY_ITEM,0,state_read,source_command,0,source_close};
 struct xw_session_handle ah,bh;assert(!xw_player_bind(&backend,&provider)&&!xw_sessions_init(&manager,31,7));
 assert(!xw_session_open(&manager,2,2,&ah)&&!xw_managed_player_bind(&a,&manager,ah,&backend));
 struct xw_player_command c={0};c.operation=XW_OP_PLAY_ITEM;assert(!xw_local_media_id_format(1,1,&c.item));
 assert(xw_managed_player_command(&a,1,&c)==XW_PLAYER_BUSY);wait_entered(1);
 assert(xw_managed_player_command(&a,1,&c)==XW_PLAYER_BUSY&&!submissions);
 assert(xw_session_revoke(&manager,ah,XW_SESSION_HOME)==XW_SESSION_PENDING);
 assert(!xw_managed_player_close(&a)&&backend.initialized);
 assert(!xw_session_open(&manager,2,2,&bh)&&!xw_managed_player_bind(&b,&manager,bh,&backend));
 uint64_t request=1;assert(!xw_local_media_id_format(1,2,&c.item));
 assert(xw_managed_player_command(&b,request,&c)==XW_PLAYER_UNAVAILABLE&&!submissions);
 atomic_store(&release_read,1);
 assert(xw_managed_player_command(&b,request,&c)==XW_PLAYER_UNAVAILABLE&&!submissions);
 assert(explicit_poll(&b,&request,&c)==XW_PLAYER_UNCERTAIN&&submissions==1);
 assert(xw_managed_player_command(&b,request,&c)==XW_PLAYER_UNCERTAIN&&submissions==1);
 assert(xw_managed_player_command(&a,2,&c)==XW_PLAYER_CLOSED&&submissions==1);
 atomic_store(&release_read,0);unsigned count=atomic_load(&entered);
 assert(!xw_local_media_id_format(1,1,&c.item));
 assert(xw_managed_player_command(&b,++request,&c)==XW_PLAYER_BUSY);wait_entered((int)count+1);
 assert(!xw_managed_player_close(&b));
 assert(xw_player_close(&backend)==XW_PLAYER_BUSY&&service.closing);
 atomic_store(&release_read,1);
 int rc=XW_PLAYER_BUSY;
 for(unsigned i=0;i<5000&&rc==XW_PLAYER_BUSY;i++){rc=xw_player_close(&backend);if(rc==XW_PLAYER_BUSY)usleep(1000);}
 assert(!rc&&!backend.initialized&&!service.bound&&submissions==1);
 assert(atomic_load(&opened)==atomic_load(&closed));
 assert(!pthread_mutex_destroy((void *)&atomic_guard));puts("MANAGED_SOURCE_ASYNC_PASS");return 0;
}
