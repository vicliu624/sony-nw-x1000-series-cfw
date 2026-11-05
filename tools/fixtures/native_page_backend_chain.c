/* Dedicated native-page chain. Do not add UI ports to the generic fixture. */
#define XW_HOST_MANAGED_MAIN unused_managed_service_main
#include "player_host_managed_service.c"
#include "../../runtime/apps/wireless-remote/settings_backend.h"
#include "../../runtime/apps/wireless-remote/native_page_bridge.h"
#include "../../runtime/platform/wireless/mode_policy.h"
#include <signal.h>
static struct wr_settings_backend backend;
static struct wr_native_page_bridge page;
static struct xw_wireless_mode_policy policy;
static struct xw_wireless_lease lease;
static unsigned view_phase,choice_posts,settings_posts;
static int begin_error,end_error;
static uint32_t reply(int rc){return WR_NATIVE_PAGE_STATUS_TAG|((uint32_t)rc&0xffffu);}
static int admit(void *context){return context==&policy&&!xw_mode_policy_data_allowed(&policy,&lease);}
static int mode(void *context){assert(context==&policy);return xw_mode_policy_admitted(&policy);}
static int prepare(void *context,uint64_t *generation){
 assert(context==&policy);uint64_t next;int rc=xw_player_host_next_generation(&next);if(rc)return rc;
 if(next>*generation)*generation=next;return 0;
}
static int begin_view(void *context){
 assert(context==&view_phase);if(begin_error)return begin_error;
 if(view_phase)return XW_PLAYER_BUSY;view_phase=1;return 0;
}
static int end_view(void *context){
 assert(context==&view_phase);if(end_error)return end_error;
 assert(view_phase==1);view_phase=2;return 0;
}
uint32_t wr_remote_page_request(uint32_t operation,uint32_t row){return wr_native_page_bridge_request(&page,operation,row);}
uint32_t wr_page_post(uint32_t event,uint32_t zero,uint32_t control,uint32_t row,uint32_t last){
 assert(event==0x20106&&!zero&&!last);
 if(control==29){assert(row<=1);choice_posts++;}
 else {assert(control==97&&row==11);settings_posts++;}
 return 0;
}
uint32_t wr_page_parent(void){return 2;}
uint32_t wr_page_index(void){return 11;}
void wr_page_set_category(uint32_t parent,uint32_t state,uint32_t zero,uint32_t index){
 assert(!zero&&index==11&&((parent==2&&state==194)||(!parent&&state==2)));
}
void wr_page_stock_home(void){}
uint32_t wr_page_set_state(uint32_t context,uint32_t group,uint32_t state){
 (void)context;assert(group==2&&state==1);return 0x0201;
}
void wr_page_stock_playback(uint32_t *group,uint32_t *state){*group=56;*state=4;}
static void *foreign(void *unused){
 (void)unused;assert(wr_native_page_bridge_request(&page,WR_NATIVE_PAGE_OPEN,0)==reply(XW_PLAYER_BUSY));
 assert(wr_native_page_bridge_request(&page,WR_NATIVE_PAGE_CANCEL,0)==reply(XW_PLAYER_BUSY));return 0;
}
static void completed(uint64_t serial,int expected){
 xw_player_host_dispatch(&original);int result=123;
 assert(!xw_player_host_settings_result(serial,&result)&&result==expected);
}
int main(void){
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR&&!pthread_mutex_init((void *)&counters,0));
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_backend};
 assert(!xw_player_bind(&original,&provider));xw_player_host_dispatch(&original);
 assert(!xw_mode_policy_init(&policy,77)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_ESPNOW,1));
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x101,&lease));
 assert(!wr_settings_backend_bind(&backend,41,&policy,admit,mode));assert(!wr_settings_backend_prepare(&backend,prepare));
 assert(!wr_native_page_bridge_bind(&page,&backend));
 assert(wr_remote_page_open()==0x0202); /* Missing view ports cannot open. */
 assert(!wr_native_page_bridge_attach_view(&page,&view_phase,begin_view,end_view));
 begin_error=XW_PLAYER_UNAVAILABLE;assert(wr_remote_page_open()==0x0202&&!page.open&&!view_phase);begin_error=0;
 pthread_t thread;assert(!pthread_create(&thread,0,foreign,0)&&!pthread_join(thread,0));
 assert(wr_remote_page_open()==0xc201&&!wr_remote_page_init(0,0,0)&&choice_posts==1);
 assert(!wr_remote_page_select(0,0,0)&&!backend.pending_enabled&&!backend.process.state);
 end_error=XW_PLAYER_BUSY;
 assert(wr_remote_page_confirm(0,0,0xff0001)==0xc202&&page.open&&view_phase==1&&!settings_posts);
 end_error=0;assert(wr_remote_page_confirm(0,0,0xff0001)==0x0201&&!page.open&&view_phase==2&&settings_posts==1);
 assert(!backend.last_request&&!backend.process.state&&!backend.pending_enabled);
 assert(wr_remote_page_open()==0x0202); /* View close not acknowledged yet. */
 view_phase=0; /* Explicit renderer-completion fixture, not native proof. */
 assert(!xw_mode_policy_release(&policy,&lease,1));
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_OFF));
 assert(wr_settings_backend_request_enabled(&backend,1)==XW_PLAYER_ACCEPTED);
 completed(1,XW_PLAYER_UNAVAILABLE);
 struct wr_settings_start_result start;
 assert(!wr_settings_backend_start_result(&backend,&start));
 assert(start.serial==1&&start.stage==WR_START_MODE&&start.result==XW_PLAYER_UNAVAILABLE&&!start.child_reaped);
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_ESPNOW));
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x101,&lease));
 assert(wr_remote_page_open()==0xc201&&!wr_remote_page_init(0,0,0)&&choice_posts==2);
 assert(!wr_remote_page_select(0,0,0));
 assert(wr_remote_page_confirm(0,0,0xff0000)==0x0201&&!page.open&&backend.pending_enabled==2&&view_phase==2);
 view_phase=0;completed(2,XW_PLAYER_ACCEPTED);
 assert(!wr_settings_backend_start_result(&backend,&start));
 assert(start.serial==2&&start.stage==WR_START_OFFERED&&start.result==XW_PLAYER_ACCEPTED&&!start.child_reaped);
 for(unsigned i=0;track==1;i++){assert(i<6000);now+=5;xw_player_host_dispatch(&original);poll(0,0,1);}
 assert(track==2&&backend.phase==WR_SETTINGS_STARTING&&original.initialized&&!backend_closed);
 assert(!wr_settings_backend_request_enabled(&backend,1)&&!backend.process.stop_sent);
 assert(wr_remote_page_open()==0xc201&&page.open&&view_phase==1);
 assert(wr_settings_backend_request_enabled(&backend,0)==XW_PLAYER_ACCEPTED);
 assert(wr_settings_backend_request_enabled(&backend,0)==XW_PLAYER_ACCEPTED);
 assert(wr_settings_backend_request_enabled(&backend,1)==XW_PLAYER_BUSY);
 completed(3,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;backend.phase!=WR_SETTINGS_RETIRED;i++){assert(i<6000);now+=5;xw_player_host_dispatch(&original);poll(0,0,1);}
 assert(backend.process.reaped&&!backend.process.status&&backend.process.state==WR_PROCESS_CLOSED);
 assert(!wr_settings_backend_start_result(&backend,&start)&&start.serial==2&&start.child_reaped&&!start.child_wait_status);
 assert(xw_player_host_service_phase()==XW_HOST_STOPPED&&!xw_mode_policy_release(&policy,&lease,1));
 fwrite(backend.process.log_tail,1,backend.process.log_bytes,stdout);
#ifdef WR_SETTINGS_RESTART
 uint64_t generation=0;assert(!xw_player_host_next_generation(&generation)&&generation==42);
 assert(!wr_settings_backend_renew(&backend,generation));
 assert(!wr_settings_backend_start_result(&backend,&start)&&start.serial==2&&start.child_reaped);
 assert(wr_native_page_bridge_request(&page,WR_NATIVE_PAGE_QUERY,0)==reply(XW_PLAYER_STALE));
 assert(wr_native_page_bridge_request(&page,WR_NATIVE_PAGE_APPLY,0)==reply(XW_PLAYER_STALE));
 puts("NATIVE_PAGE_GENERATION_STALE_PASS");
#endif
 assert(wr_native_page_bridge_request(&page,WR_NATIVE_PAGE_CANCEL,0)==reply(0));view_phase=0;
 assert(!wr_native_page_bridge_unbind(&page)&&!page.view_begin&&!page.view_context);
 assert(!wr_settings_backend_unbind(&backend));
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);pthread_mutex_unlock((void *)&counters);
 assert(!xw_player_close(&original)&&!pthread_mutex_destroy((void *)&counters));
 puts("NATIVE_PAGE_BACKEND_CHAIN_PASS");puts("PUBLIC_MANAGED_HOST_SERVER_PASS");return 0;
}
