/* Actual Settings queue/backend/process/Supervisor chain; Sony/media modeled. */
#define XW_HOST_MANAGED_MAIN managed_service_regression_main
#include "player_host_managed_service.c"
#include "../../runtime/apps/wireless-remote/settings_backend.h"
#include "../../runtime/platform/wireless/mode_policy.h"
#include <signal.h>
static int permitted,stop_probe;
static struct xw_wireless_mode_policy policy;
static struct xw_wireless_lease radio_lease;
static int policy_available=1;
#ifdef WR_SETTINGS_ADMISSION_TEST
static int player_admission=1;
int xw_player_host_wireless_player_active(void){return player_admission;}
#endif
#ifdef WR_SETTINGS_RESTART
static uint64_t run_session(const struct wr_settings_backend *b){
 const char *p=strstr(b->process.log_tail,"REMOTE_CHAIN_SESSION=");assert(p);p+=sizeof("REMOTE_CHAIN_SESSION=")-1;
 uint64_t value=0;while(*p>='0'&&*p<='9'){unsigned d=(unsigned)(*p++-'0');assert(value<=(UINT64_MAX-d)/10);value=value*10+d;}assert(value);return value;
}
#endif
static int admit_backend(void *context){return context==&permitted&&permitted==1&&
 !xw_mode_policy_data_allowed(&policy,&radio_lease);}
static int wireless_mode(void *context){assert(context==&permitted);return policy_available?xw_mode_policy_admitted(&policy):XW_WIRELESS_MODE_UNKNOWN;}
static int prepare_generation(void *context,uint64_t *generation){
 assert(context==&permitted);uint64_t next;int rc=xw_player_host_next_generation(&next);if(rc)return rc;
 if(next>*generation)*generation=next;return 0;
}
static void submit(uint64_t serial,int expected){
 assert(xw_player_host_settings_enqueue()==XW_PLAYER_ACCEPTED);xw_player_host_dispatch(&original);
 int result=123;assert(!xw_player_host_settings_result(serial,&result)&&result==expected);
}
static void *probe_thread(void *unused){
 (void)unused;for(;;){pthread_mutex_lock((void *)&counters);int stopped=stop_probe;pthread_mutex_unlock((void *)&counters);if(stopped)return 0;poll(0,0,1);}
}
static void *foreign_settings_query(void *context){
 struct wr_settings_backend *b=context;
 struct wr_settings_view view={99,99,99,99};
 assert(wr_settings_backend_query(b,&view)==XW_PLAYER_BUSY);
 assert(view.phase==99&&view.pending==99&&view.requested_enabled==99&&view.error==99);
 assert(wr_settings_backend_request_enabled(b,1)==XW_PLAYER_BUSY);
 return 0;
}
int main(void){
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);
 assert(!pthread_mutex_init((void *)&counters,0));
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_backend};
 assert(!xw_player_bind(&original,&provider));xw_player_host_dispatch(&original);
#ifdef WR_SETTINGS_ADMISSION_TEST
 player_admission=0;
 assert(xw_player_host_settings_enqueue()==XW_PLAYER_CLOSED);
 assert(xw_player_host_session_offer(-1,3,3,41)==XW_PLAYER_CLOSED);
 player_admission=1;
#endif
 assert(!xw_mode_policy_init(&policy,77)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_OFF,1)); /* Modeled original-off evidence. */
 pthread_t thread;assert(!pthread_create(&thread,0,probe_thread,0));
 struct wr_settings_backend backend={0};assert(!wr_settings_backend_bind(&backend,41,&permitted,admit_backend,wireless_mode));
 assert(!wr_settings_backend_prepare(&backend,prepare_generation));
 pthread_t foreign;assert(!pthread_create(&foreign,0,foreign_settings_query,&backend)&&!pthread_join(foreign,0));
 struct wr_settings_view view;
 for(unsigned i=0;i<1000;i++){
  assert(!wr_settings_backend_query(&backend,&view));
  assert(view.phase==WR_SETTINGS_OFF&&!view.pending&&!view.requested_enabled);
 }
 assert(!backend.last_request&&!backend.process.state&&!opened);
 assert(!wr_settings_backend_request_enabled(&backend,0));
 assert(wr_settings_backend_request_enabled(&backend,2)==XW_PLAYER_INVALID);
 permitted=1;submit(1,XW_PLAYER_UNAVAILABLE);
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI));submit(2,XW_PLAYER_UNAVAILABLE);
 policy_available=0;submit(3,XW_PLAYER_UNAVAILABLE);policy_available=1;
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_ESPNOW));permitted=0;submit(4,XW_PLAYER_UNAVAILABLE);
 assert(backend.phase==WR_SETTINGS_OFF&&!backend.process.state&&!opened);
 permitted=1;assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x101,&radio_lease));
 assert(wr_settings_backend_request_enabled(&backend,1)==XW_PLAYER_ACCEPTED);
 assert(wr_settings_backend_request_enabled(&backend,1)==XW_PLAYER_ACCEPTED);
 assert(wr_settings_backend_request_enabled(&backend,0)==XW_PLAYER_BUSY);
 assert(!wr_settings_backend_query(&backend,&view)&&view.pending&&view.requested_enabled==1);
 xw_player_host_dispatch(&original);int enabled_result=123;
 assert(!xw_player_host_settings_result(5,&enabled_result)&&enabled_result==XW_PLAYER_ACCEPTED);
#ifdef WR_SETTINGS_EARLY_STOP
 /* submit() already ran the first launch tick. */
#else
 for(unsigned i=0;track==1;i++){assert(i<6000);now+=5;xw_player_host_dispatch(&original);poll(0,0,1);}
 assert(track==2);
#endif
 assert(backend.phase==WR_SETTINGS_STARTING&&original.initialized&&!backend_closed);
 assert(!wr_settings_backend_query(&backend,&view)&&view.requested_enabled==1);
 assert(!wr_settings_backend_request_enabled(&backend,1));
 assert(backend.phase==WR_SETTINGS_STARTING&&!backend.process.stop_sent);
 uint64_t unavailable_generation=999;assert(xw_player_host_next_generation(&unavailable_generation)==XW_PLAYER_BUSY&&unavailable_generation==999);
 uint64_t next_serial=6;
#ifdef WR_SETTINGS_MODE_SWITCH
 assert(xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
 assert(policy.state.selected==XW_WIRELESS_MODE_ESPNOW&&policy.state.active);
 struct xw_wireless_lease premature;
 assert(xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_WIFI,0x202,&premature)==XW_MODE_DENIED);
#else
 assert(wr_settings_backend_request_enabled(&backend,0)==XW_PLAYER_ACCEPTED);
 assert(wr_settings_backend_request_enabled(&backend,0)==XW_PLAYER_ACCEPTED);
 assert(wr_settings_backend_request_enabled(&backend,1)==XW_PLAYER_BUSY);
 xw_player_host_dispatch(&original);int explicit_result=123;
 assert(!xw_player_host_settings_result(next_serial++,&explicit_result)&&explicit_result==XW_PLAYER_ACCEPTED);
#endif
 for(unsigned i=0;backend.phase!=WR_SETTINGS_RETIRED;i++){assert(i<6000);now+=5;xw_player_host_dispatch(&original);poll(0,0,1);}
 assert(xw_player_host_service_phase()==XW_HOST_STOPPED&&backend.process.reaped&&backend.process.status==0&&backend.process.state==WR_PROCESS_CLOSED);
 assert(track>=1&&track<=2&&original.initialized&&!backend_closed);
 assert(policy.state.active); /* Consumer retirement is not automatic policy release. */
 assert(!xw_mode_policy_release(&policy,&radio_lease,1)); /* Modeled owner off receipt. */
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);stop_probe=1;pthread_mutex_unlock((void *)&counters);
 assert(!pthread_join(thread,0));
 /* A pinned finite profile is not silently reused as a new generation. */
 submit(next_serial,XW_PLAYER_STALE);
#ifdef WR_SETTINGS_RESTART
 uint64_t old_session=run_session(&backend);int old_child=backend.process.child;
 assert(wr_settings_backend_renew(&backend,41)==XW_PLAYER_STALE);
 uint64_t new_generation=0;assert(!xw_player_host_next_generation(&new_generation)&&new_generation==42);
 assert(!wr_settings_backend_renew(&backend,new_generation)&&backend.phase==WR_SETTINGS_OFF);
 assert(wr_settings_backend_renew(&backend,43)==XW_PLAYER_BUSY);
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x101,&radio_lease));
 unsigned previous_track=track;submit(++next_serial,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;track==previous_track;i++){assert(i<6000);now+=5;xw_player_host_dispatch(&original);poll(0,0,1);}
 assert(track==previous_track+1&&backend.process.child!=old_child);
 submit(++next_serial,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;backend.phase!=WR_SETTINGS_RETIRED;i++){assert(i<6000);now+=5;xw_player_host_dispatch(&original);poll(0,0,1);}
 assert(backend.generation==42&&backend.process.reaped&&backend.process.status==0&&backend.process.state==WR_PROCESS_CLOSED);
 assert(run_session(&backend)!=old_session&&xw_player_host_service_phase()==XW_HOST_STOPPED);
 assert(!xw_mode_policy_release(&policy,&radio_lease,1));
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);pthread_mutex_unlock((void *)&counters);
 puts("SETTINGS_BACKEND_RESTART_PASS");
#endif
#ifdef WR_SETTINGS_MODE_SWITCH
 assert(xw_mode_policy_admitted(&policy)==XW_WIRELESS_MODE_WIFI);
#else
 assert(xw_mode_policy_admitted(&policy)==XW_WIRELESS_MODE_ESPNOW);
#endif
 /* Another generic consumer can acquire without reopening the player SDK. */
#ifdef WR_SETTINGS_ADMISSION_TEST
 uint64_t old_request=backend.last_request;
 assert(xw_player_host_settings_enqueue()==XW_PLAYER_ACCEPTED);player_admission=0;
 xw_player_host_dispatch(&original);int cancelled=0;
 assert(!xw_player_host_settings_result(next_serial+1,&cancelled)&&cancelled==XW_PLAYER_CLOSED&&backend.last_request==old_request);
 player_admission=1;puts("SETTINGS_BACKEND_ADMISSION_PASS");
#endif
 struct xw_wireless_lease other;int mode=xw_mode_policy_admitted(&policy);
 assert(!xw_mode_policy_acquire(&policy,mode,0x202,&other));
 assert(xw_mode_policy_release(&policy,&radio_lease,1)==XW_MODE_STALE);
 assert(xw_player_host_service_phase()==XW_HOST_STOPPED&&!xw_mode_policy_release(&policy,&other,1));
 fwrite(backend.process.log_tail,1,backend.process.log_bytes,stdout);
 assert(!wr_settings_backend_unbind(&backend));assert(!xw_player_close(&original));
 assert(!pthread_mutex_destroy((void *)&counters));
 puts("SETTINGS_BACKEND_CHAIN_PASS");puts("PUBLIC_MANAGED_HOST_SERVER_PASS");return 0;
}
