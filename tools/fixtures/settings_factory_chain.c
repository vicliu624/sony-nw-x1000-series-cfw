/* Real factory/backend/process/service/SDK/policy; native Wi-Fi/RF modeled. */
#define XW_HOST_MANAGED_MAIN managed_service_regression_main
#include "player_host_managed_service.c"
#include "../../runtime/apps/wireless-remote/settings_factory.h"
#include "../../runtime/apps/wireless-remote/owner_admission.h"
#include "../../runtime/platform/player/wireless_host.h"
#include "../../runtime/platform/wireless/native_delivery.h"
#include "../../runtime/platform/wireless/native_retirement.h"
#include <signal.h>
#ifdef WR_SETTINGS_AUTO_TEST
#define FIRST_REMOTE 1
#define FOREIGN_REMOTE 2
#define SECOND_REMOTE 3
#define LAST_REMOTE 4
#else
#define FIRST_REMOTE 41
#define FOREIGN_REMOTE 42
#define SECOND_REMOTE 43
#define LAST_REMOTE 44
static struct wr_settings_factory factory;
#endif
static struct xw_wireless_mode_policy policy;
static int permitted=1;
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
static uint64_t sessions[4],last_retired;
#else
static uint64_t sessions[3],last_retired;
#endif
static unsigned cycles;
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
#include "../../runtime/platform/player/sleep_host.h"
static struct xw_sleep_host sleep_gate;
static uint64_t sleep_epoch;
static unsigned sleep_acks;
static int sleep_valid(void *p,uint64_t epoch){return p==&sleep_gate&&epoch==sleep_epoch&&!xw_player_host_original_exiting()?0:XW_PLAYER_STALE;}
static int sleep_ack(void *p);
static int sleep_recovery_valid(void *p,uint64_t epoch){return p==&sleep_gate&&epoch==sleep_epoch?0:XW_PLAYER_STALE;}
static int sleep_recovery_stale(void *p,uint64_t epoch){(void)p;(void)epoch;return XW_PLAYER_STALE;}
#endif
int xw_native_rf_gui_owner(void){assert(0);return 0;}
int xw_native_rf_stop_request(void){assert(0);return -1;}
int xw_player_host_wireless_initialization_status(void){assert(0);return -1;}
int xw_native_rf_publish(struct xw_wireless_mode_policy *p,int fd,const struct xw_wireless_lease *l){(void)p;(void)fd;(void)l;assert(0);return -1;}
int xw_native_rf_retirement_receive(struct xw_native_retirement *r){(void)r;assert(0);return -1;}
#ifdef WR_SETTINGS_AUTO_TEST
int xw_player_remote_software_ready(void){return permitted;}
int xw_player_remote_state_active(void){return xw_player_host_wireless_player_active()&&!xw_player_host_original_exiting();}
#include "../../runtime/platform/player/remote_auto.c"
#else
static int qualified(void *context){assert(context==&permitted);return permitted;}
#endif
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
static int sleep_ack(void *p){
 assert(p==&sleep_gate&&!factory.held&&!policy.state.active&&policy.state.off_verified);
 assert(xw_player_host_service_phase()==XW_HOST_STOPPED);
 assert(factory.backend.phase==WR_SETTINGS_RETIRED&&factory.backend.process.status==0);
 sleep_acks++;return 0;
}
#endif
static void capture_retired(void){
 if(factory.backend.phase==WR_SETTINGS_RETIRED&&last_retired!=factory.backend.generation){
  assert(!factory.backend.process.mode_view_configured);
  last_retired=factory.backend.generation;
#ifdef WR_REAL_OWNER_REFUSAL
  assert(factory.backend.process.startup_refused);cycles++;
  fwrite(factory.backend.process.log_tail,1,factory.backend.process.log_bytes,stdout);fflush(stdout);return;
#endif
  assert(cycles<sizeof sessions/sizeof *sessions);const char *p=strstr(factory.backend.process.log_tail,"REMOTE_CHAIN_SESSION=");assert(p);p+=sizeof("REMOTE_CHAIN_SESSION=")-1;
  uint64_t n=0;while(*p>='0'&&*p<='9'){unsigned d=(unsigned)(*p++-'0');assert(n<=(UINT64_MAX-d)/10);n=n*10+d;}assert(n);
  sessions[cycles++]=n;fwrite(factory.backend.process.log_tail,1,factory.backend.process.log_bytes,stdout);fflush(stdout);
 }
}
static void pump(void){
 now+=5;xw_player_host_dispatch(&original);capture_retired();
#ifdef WR_SETTINGS_AUTO_TEST
 xw_player_host_remote_auto();int tick=factory.fault_latched?factory.error:0;
#else
 int tick=wr_settings_factory_tick(&factory);
#endif
 if(tick)fprintf(stderr,"factory tick=%d backend=%u error=%d child_state=%d child_status=%d host=%u policy=%u held=%u\n%.*s\n",tick,factory.backend.phase,factory.backend.error,factory.backend.process.state,factory.backend.process.status,xw_player_host_service_phase(),policy.state.phase,factory.held,(int)factory.backend.process.log_bytes,factory.backend.process.log_tail);
 assert(!tick);capture_retired();poll(0,0,1);
}
static void submit(uint64_t serial,int expected){
 assert(xw_player_host_settings_enqueue()==XW_PLAYER_ACCEPTED);pump();int result=0;
 assert(!xw_player_host_settings_result(serial,&result)&&result==expected);
}
static void retired(void){
 for(unsigned i=0;factory.held||factory.backend.phase!=WR_SETTINGS_OFF;i++){assert(i<6000);pump();}
 assert(xw_player_host_service_phase()==XW_HOST_STOPPED&&!policy.state.active&&policy.state.off_verified);
 assert(!factory.owner_view.policy&&factory.owner_view_client<0);
 pthread_mutex_lock((void *)&counters);assert(opened==closed&&!live);pthread_mutex_unlock((void *)&counters);
}
static void verify_owner_view(void){
 int fd=-1;struct xw_wireless_lease lease={0},before=lease;
 assert(wr_settings_factory_owner_view(&factory,factory.backend.generation+1,&fd,&lease)==XW_PLAYER_STALE);
 assert(fd==-1&&!memcmp(&lease,&before,sizeof lease));
 assert(!wr_settings_factory_owner_view(&factory,factory.backend.generation,&fd,&lease));
 assert(fd>=3&&lease.consumer==XW_PLAYER_REMOTE_CONSUMER&&lease.serial==factory.radio.serial);
 /* Forwarded datagrams have one client/serial stream. The child exercises
  * admission; a parent diagnostic must not consume its replies. */
 if(factory.forward_owner_view){puts("FACTORY_OWNER_VIEW_PASS");return;}
 struct wr_owner_admission admission={0};assert(!wr_owner_admission_open(&admission,fd,&lease));
 assert(!wr_owner_admission_allowed(&admission)&&!wr_owner_admission_refresh(&admission));
 int rc=XW_MODE_PENDING;
 for(unsigned i=0;rc==XW_MODE_PENDING;i++){assert(i<30);rc=wr_owner_admission_step(&admission);if(rc==XW_MODE_PENDING)pump();}
 assert(!rc&&wr_owner_admission_allowed(&admission));
 assert(wr_owner_admission_close(&admission)>=0&&policy.state.active&&factory.held);
 puts("FACTORY_OWNER_VIEW_PASS");
}
int main(void){
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);assert(!pthread_mutex_init((void *)&counters,0));
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_backend};
 assert(!xw_player_bind(&original,&provider));
#ifdef WR_SETTINGS_AUTO_TEST
 xw_player_host_remote_auto();assert(!factory.initialized);
#endif
 xw_player_host_dispatch(&original);
 assert(!xw_mode_policy_init(&policy,77)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_OFF,1));
 assert(!xw_player_host_wireless_bound(&policy));
 #ifdef WR_SETTINGS_AUTO_TEST
 xw_player_host_remote_auto();assert(factory.initialized&&factory.backend.phase==WR_SETTINGS_OFF&&!factory.held&&!factory.backend.process.state);
#else
 assert(!wr_settings_factory_bind(&factory,FIRST_REMOTE,&permitted,qualified));
#endif
 #ifdef WR_REAL_OWNER_REFUSAL
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_ESPNOW));
 for(unsigned attempt=0;attempt<2;attempt++){
  submit(attempt+1,XW_PLAYER_ACCEPTED);retired();
  assert(cycles==attempt+1&&!factory.fault_latched&&factory.backend.generation==FIRST_REMOTE+attempt+1);
  assert(track==1&&!xw_player_host_resources_idle());
 }
 assert(!wr_settings_factory_unbind(&factory)&&!xw_player_host_wireless_backend_close());
 assert(!xw_player_close(&original)&&!pthread_mutex_destroy((void *)&counters));
 puts("FACTORY_START_REFUSAL_RETRY_PASS");puts("PUBLIC_MANAGED_HOST_SERVER_PASS");return 0;
 #endif
 submit(1,XW_PLAYER_UNAVAILABLE);assert(!factory.held);
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI));submit(2,XW_PLAYER_UNAVAILABLE);
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_ESPNOW));permitted=0;submit(3,XW_PLAYER_UNAVAILABLE);assert(!policy.state.active);
 permitted=1;submit(4,XW_PLAYER_ACCEPTED);assert(factory.held&&policy.state.lease.consumer==XW_PLAYER_REMOTE_CONSUMER);
 assert(xw_player_host_resources_idle()==XW_PLAYER_BUSY);
 for(unsigned i=0;track==1;i++){assert(i<6000);pump();}assert(track==2);
 verify_owner_view();
 submit(5,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;xw_player_host_service_phase()!=XW_HOST_STOPPED;i++){assert(i<6000);pump();}
 assert(factory.backend.phase==WR_SETTINGS_STOPPING);
 int delivery[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 assert(!xw_player_host_session_offer(delivery[0],1,1,FOREIGN_REMOTE));close(delivery[0]);
 pump();
 assert(factory.backend.phase==WR_SETTINGS_RETIRED&&!factory.held&&xw_player_host_service_phase()==XW_HOST_ACTIVE);
 assert(xw_player_host_generation_retired(FIRST_REMOTE)==1&&xw_player_host_service_stop_generation(FIRST_REMOTE)==XW_PLAYER_STALE);
 assert(xw_player_host_service_phase()==XW_HOST_ACTIVE);close(delivery[1]);
 int stopping=xw_player_host_service_stop_generation(FOREIGN_REMOTE);assert(stopping==0||stopping==XW_PLAYER_BUSY);
 retired();assert(cycles==1&&factory.backend.generation==SECOND_REMOTE);
 struct xw_wireless_lease other;assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x202,&other));
 submit(6,XW_PLAYER_UNAVAILABLE);assert(!factory.held&&!xw_mode_policy_data_allowed(&policy,&other));
 assert(!xw_mode_policy_release(&policy,&other,1));submit(7,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;track==2;i++){assert(i<6000);pump();}assert(track==3);
 assert(xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
 retired();assert(cycles==2&&sessions[0]!=sessions[1]&&policy.state.selected==XW_WIRELESS_MODE_WIFI&&factory.backend.generation==LAST_REMOTE);
 assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_ESPNOW));submit(8,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;track==3;i++){assert(i<6000);pump();}assert(track==4);
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
 struct xw_wireless_lease before_sleep=policy.state.lease;
 assert(!xw_player_host_wireless_next_epoch(&sleep_epoch)&&sleep_epoch);
 assert(xw_player_sleep_host_begin(&sleep_gate,&sleep_gate,sleep_valid,sleep_ack,sleep_epoch,pthread_self())==XW_PLAYER_ACCEPTED);
 int sleep_result=XW_PLAYER_ACCEPTED;
 for(unsigned i=0;sleep_result==XW_PLAYER_ACCEPTED;i++){
  assert(i<6000&&!sleep_acks);pump();sleep_result=xw_player_sleep_host_poll(&sleep_gate);
 }
 assert(!sleep_result&&sleep_acks==1&&sleep_gate.retirement.phase==XW_SLEEP_ACKNOWLEDGED);
 assert(!xw_player_sleep_host_poll(&sleep_gate)&&sleep_acks==1);
 assert(xw_player_host_settings_enqueue()==XW_PLAYER_CLOSED);
 puts("SLEEP_RETIREMENT_CHAIN_PASS");
 assert(!xw_player_host_resources_idle());
 assert(xw_player_sleep_host_resume(&sleep_gate,sleep_recovery_stale)==XW_PLAYER_STALE);
 assert(!xw_player_host_wireless_player_active()&&!policy.state.active);
 struct xw_wireless_lease during_sleep;
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x999,&during_sleep));
 assert(xw_player_sleep_host_resume(&sleep_gate,sleep_recovery_valid)==XW_PLAYER_ACCEPTED);
 assert(!xw_mode_policy_data_allowed(&policy,&during_sleep)&&!xw_player_host_wireless_player_active());
 assert(!xw_mode_policy_release(&policy,&during_sleep,1));
 assert(!xw_player_sleep_host_resume(&sleep_gate,sleep_recovery_valid));
 assert(sleep_gate.retirement.phase==XW_SLEEP_IDLE&&xw_player_host_wireless_player_active());
 retired();assert(cycles==3&&factory.backend.generation==LAST_REMOTE+1);
 submit(9,XW_PLAYER_ACCEPTED);
 for(unsigned i=0;track==4;i++){assert(i<6000);pump();}assert(track==5);
 assert(factory.backend.generation==LAST_REMOTE+1&&factory.held);
 verify_owner_view();
 assert(xw_player_host_generation_retired(LAST_REMOTE)==1);
 assert(xw_player_host_service_stop_generation(LAST_REMOTE)==XW_PLAYER_STALE&&xw_player_host_service_phase()==XW_HOST_ACTIVE);
 assert(xw_player_host_wireless_remote_retired(&before_sleep,1)==XW_MODE_STALE&&policy.state.active);
 puts("SLEEP_REMOTE_RESTART_PASS");
#endif
 int native_stop=xw_player_host_service_quiesce();assert(!native_stop||native_stop==XW_PLAYER_BUSY);
 xw_player_host_note_native_exit();
 assert(xw_player_host_wireless_prepare_stop(200)==XW_MODE_PENDING);
 for(unsigned i=0;factory.held||factory.backend.phase!=WR_SETTINGS_RETIRED||xw_player_host_service_phase()!=XW_HOST_STOPPED;i++){assert(i<6000);pump();}
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
 assert(cycles==4&&factory.backend.generation==LAST_REMOTE+1);
 for(unsigned i=0;i<cycles;i++)for(unsigned j=0;j<i;j++)assert(sessions[i]!=sessions[j]);
#else
 assert(cycles==3&&sessions[2]!=sessions[1]&&sessions[2]!=sessions[0]&&factory.backend.generation==LAST_REMOTE);
#endif
 assert(!xw_player_host_wireless_prepare_stop(200)&&xw_player_host_settings_enqueue()==XW_PLAYER_CLOSED);
 assert(original.initialized&&!backend_closed&&!wr_settings_factory_unbind(&factory));
 assert(!xw_player_host_wireless_backend_close()&&!xw_player_close(&original));assert(!pthread_mutex_destroy((void *)&counters));
 puts("SETTINGS_FACTORY_CHAIN_PASS");puts("SETTINGS_BACKEND_CHAIN_PASS");puts("SETTINGS_BACKEND_RESTART_PASS");puts("PUBLIC_MANAGED_HOST_SERVER_PASS");return 0;
}
