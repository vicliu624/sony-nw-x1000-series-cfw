#include "../runtime/platform/wireless/mode_policy.h"
#include "../runtime/platform/wireless/native_setting.h"
#include "../runtime/platform/wireless/native_owner.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/wait.h>
static void *foreign(void *context){
 struct xw_wireless_mode_policy *p=context;struct xw_wireless_mode_snapshot s,copy;
 memset(&s,0x5a,sizeof s);copy=s;
 assert(xw_mode_policy_snapshot(p,&s)==XW_MODE_WRONG_OWNER&&!memcmp(&s,&copy,sizeof s));
 assert(xw_mode_policy_request(p,XW_WIRELESS_MODE_OFF)==XW_MODE_WRONG_OWNER);
 assert(xw_mode_policy_admitted(p)==XW_WIRELESS_MODE_UNKNOWN);return 0;
}
static void native_settings(void){
 for(unsigned row=0;row<3;row++){
  struct xw_wireless_mode_policy p={0};struct xw_wireless_native_setting s={0};struct xw_wireless_lease lease;
  assert(!xw_mode_policy_init(&p,99)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_OFF,1));
  assert(!xw_wireless_setting_open(&s,&p));
  assert(xw_wireless_setting_request(&s,5,0)==0x574e0001u);
  assert(!xw_wireless_setting_select(&s,row)&&xw_wireless_setting_row(s.preview)==(int)row);
  assert(p.state.selected==XW_WIRELESS_MODE_OFF&&!p.state.active);
  assert(!xw_wireless_setting_cancel(&s)&&s.preview==XW_WIRELESS_MODE_OFF);
  assert(xw_wireless_setting_select(&s,3)==XW_MODE_INVALID);
  assert(!xw_wireless_setting_select(&s,row)&&!xw_wireless_setting_confirm(&s));
  assert(p.state.selected==s.preview&&p.state.off_verified&&!p.state.active);
  assert(xw_wireless_setting_request(&s,5,0)==(0x574e0000u|row));
  if(s.preview==XW_WIRELESS_MODE_OFF)continue;
  assert(!xw_mode_policy_acquire(&p,s.preview,7,&lease));
  assert(!xw_wireless_setting_select(&s,1)&&xw_wireless_setting_confirm(&s)==XW_MODE_PENDING);
  assert(xw_wireless_setting_request(&s,5,0)==0x574dfffbu);
  assert(xw_wireless_setting_request(&s,2,1)==0x574d0001u);
  assert(xw_wireless_setting_request(&s,2,row)==0x574dfffbu);
  assert(xw_wireless_setting_request(&s,4,1)==0x574dfffbu);
  assert(xw_wireless_setting_confirm(&s)==XW_MODE_PENDING&&xw_wireless_setting_cancel(&s)==XW_MODE_BUSY);
  assert(xw_wireless_setting_select(&s,row)==XW_MODE_BUSY&&xw_wireless_setting_poll(&s)==XW_MODE_PENDING);
  assert(!xw_mode_policy_release(&p,&lease,1)&&xw_wireless_setting_request(&s,2,1)==0x574d0000u&&!s.pending);
  assert(p.state.selected==XW_WIRELESS_MODE_OFF);
  assert(!xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW));
  assert(xw_wireless_setting_confirm(&s)==XW_MODE_STALE&&xw_wireless_setting_poll(&s)==XW_MODE_STALE);
 }
 assert(xw_wireless_setting_row(XW_WIRELESS_MODE_UNKNOWN)==-1);
}
struct queue_fixture {unsigned queued,stops,checks;int result,retirement;uint32_t message[4];};
static int native_queue(void *context,const uint32_t message[4]){
 struct queue_fixture *f=context;f->queued++;memcpy(f->message,message,16);return f->result;
}
static int native_stop(void *context,const struct xw_wireless_lease *lease){
 struct queue_fixture *f=context;assert(lease->mode==XW_WIRELESS_MODE_WIFI&&lease->consumer==808);f->stops++;return 0;
}
static int native_retirement(void *context,const struct xw_wireless_lease *lease){
 struct queue_fixture *f=context;assert(lease->consumer==808);f->checks++;return f->retirement;
}
static void native_owner(void){
 struct xw_wireless_mode_policy p={0};struct xw_native_wireless_owner n={0};struct queue_fixture f={0};
 uint32_t message[4]={0,0x4c0007,0x12345678,0x87654321};
 assert(!xw_mode_policy_init(&p,200)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 assert(!xw_native_wireless_bind(&n,&p,808,&f,native_queue,native_stop,native_retirement));
 assert(!xw_native_wireless_submit(&n,message)&&n.held&&f.queued==1&&!memcmp(message,f.message,16));
 assert(!xw_native_wireless_submit(&n,message)&&f.queued==2&&p.serial==1);
 assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);
 f.retirement=XW_MODE_PENDING;
 assert(xw_native_wireless_poll(&n)==XW_MODE_PENDING&&f.stops==1&&!f.checks);
 assert(xw_native_wireless_submit(&n,message)==XW_MODE_DENIED&&f.queued==2);
 assert(xw_native_wireless_poll(&n)==XW_MODE_PENDING&&f.stops==1&&n.held);
 f.retirement=0;assert(!xw_native_wireless_poll(&n)&&!n.held&&p.state.selected==XW_WIRELESS_MODE_ESPNOW);
 assert(xw_native_wireless_submit(&n,message)==XW_MODE_DENIED);
 assert(!xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI)&&!xw_native_wireless_submit(&n,message)&&p.serial==2);
 assert(xw_native_wireless_stop(&n)==XW_MODE_PENDING&&!xw_native_wireless_poll(&n)&&p.state.selected==XW_WIRELESS_MODE_WIFI);
 f.result=-1;assert(xw_native_wireless_submit(&n,message)==XW_MODE_FAULT&&n.held&&p.state.active&&p.state.phase==XW_MODE_FAILED);
 assert(xw_native_wireless_poll(&n)==XW_MODE_FAULT&&xw_native_wireless_submit(&n,message)==XW_MODE_FAULT);
 struct xw_wireless_mode_policy stock={0};struct xw_native_wireless_owner adopted={0};struct xw_wireless_lease lease;
 assert(!xw_mode_policy_init(&stock,201)&&!xw_mode_policy_adopt_wifi(&stock,808,1,&lease));
 assert(!xw_native_wireless_bind(&adopted,&stock,808,&f,native_queue,native_stop,native_retirement));
 assert(!xw_native_wireless_adopt(&adopted,&lease)&&adopted.held);
 f.result=0;assert(!xw_native_wireless_submit(&adopted,message)&&stock.serial==1);
 assert(xw_native_wireless_stop(&adopted)==XW_MODE_PENDING);
 f.retirement=-1;assert(xw_native_wireless_poll(&adopted)==XW_MODE_FAULT&&adopted.held&&stock.state.active);
}
int main(void){
 native_owner();
 native_settings();
 struct xw_wireless_mode_policy p={0};struct xw_wireless_lease a,b,poison;
 memset(&a,0x5a,sizeof a);poison=a;
 assert(!xw_mode_policy_init(&p,77)&&xw_mode_policy_admitted(&p)==XW_WIRELESS_MODE_UNKNOWN);
 assert(xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,101,&a)==XW_MODE_DENIED&&!memcmp(&a,&poison,sizeof a));
 assert(xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_OFF,0)==XW_MODE_DENIED);
 assert(!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_OFF,1));
 assert(!xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI)&&p.state.off_verified);
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,101,&a)&&!p.state.off_verified);
 assert(xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,202,&b)==XW_MODE_BUSY);
 assert(!xw_mode_policy_data_allowed(&p,&a));
 assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);
 assert(p.state.selected==XW_WIRELESS_MODE_WIFI&&p.state.requested==XW_WIRELESS_MODE_ESPNOW);
 assert(xw_mode_policy_admitted(&p)==XW_WIRELESS_MODE_UNKNOWN&&!xw_mode_policy_owns(&p,&a));
 assert(xw_mode_policy_data_allowed(&p,&a)==XW_MODE_DENIED);
 assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING&&p.state.phase==XW_MODE_DRAINING);
 assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);
 assert(xw_mode_policy_release(&p,&a,0)==XW_MODE_FAULT&&p.state.active);
 assert(!xw_mode_policy_owns(&p,&a)&&xw_mode_policy_request(&p,XW_WIRELESS_MODE_OFF)==XW_MODE_FAULT);
 assert(!xw_mode_policy_release(&p,&a,1)&&!p.state.active&&p.state.phase==XW_MODE_FAILED);
 assert(xw_mode_policy_admitted(&p)==XW_WIRELESS_MODE_UNKNOWN);
 assert(!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_ESPNOW,1));
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,202,&b)&&b.serial>a.serial);
 assert(xw_mode_policy_release(&p,&a,1)==XW_MODE_STALE&&p.state.active);
 struct xw_wireless_lease wrong=b;wrong.consumer++;
 assert(xw_mode_policy_release(&p,&wrong,1)==XW_MODE_STALE);
 assert(!xw_mode_policy_release(&p,&b,1)&&xw_mode_policy_admitted(&p)==XW_WIRELESS_MODE_ESPNOW);
 assert(!p.state.active&&p.state.off_verified);
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,303,&b));
 assert(!xw_mode_policy_release(&p,&b,1));
 pthread_t thread;assert(!pthread_create(&thread,0,foreign,&p)&&!pthread_join(thread,0));
 pid_t child=fork();assert(child>=0);if(!child){assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_OFF)==XW_MODE_WRONG_OWNER);_exit(0);}
 int status;assert(waitpid(child,&status,0)==child&&!status);
 p.serial=UINT64_MAX;assert(xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,404,&b)==XW_MODE_DENIED);
 struct xw_wireless_mode_policy stock={0};assert(!xw_mode_policy_init(&stock,88));
 assert(xw_mode_policy_adopt_wifi(&stock,1,0,&a)==XW_MODE_DENIED);
 assert(!xw_mode_policy_adopt_wifi(&stock,1,1,&a)&&stock.state.active&&!stock.state.off_verified);
 assert(xw_mode_policy_request(&stock,XW_WIRELESS_MODE_OFF)==XW_MODE_PENDING);
 assert(!xw_mode_policy_release(&stock,&a,1)&&xw_mode_policy_admitted(&stock)==XW_WIRELESS_MODE_OFF);
 assert(xw_mode_policy_request(&stock,XW_WIRELESS_MODE_UNKNOWN)==XW_MODE_INVALID);
 puts("WIRELESS_MODE_POLICY_PASS");return 0;
}
