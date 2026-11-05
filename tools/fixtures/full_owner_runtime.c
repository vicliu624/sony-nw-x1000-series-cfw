#define FULL_OWNER_IPC_MAIN ipc_checks
#include "full_owner_ipc.c"
#include "../../runtime/platform/espnow/xnow_owner_runtime.h"
#ifdef XNOW_TEST_MODE_ADMISSION
#include "../../runtime/apps/wireless-remote/owner_admission.h"
#include <sys/socket.h>
#endif
#ifdef XNOW_TEST_POWER_OFF
#include "../../runtime/apps/wireless-remote/radio_stop.h"
#define FINAL_CONNECTION 2
#define FINAL_INITIALIZED 0
static unsigned power_off_calls;
int xw_wireless_modules_unloaded(void){return 1;}
int cnmgr_power_off(void){assert(clients&&connection==3&&fixture_radio_kind==0&&fixture_initialized);power_off_calls++;connection=2;fixture_initialized=0;return 0;}
static int exclusive_power(void *context){return xnow_owner_gate_radio_valid(context);}
static int advance_power(void *context,struct xnow_full_control *c){return c->stop_requested?wr_radio_stop_step(c,context,exclusive_power):xnow_full_control_step(c);}
static int tick(struct xnow_owner_runtime *r){return xnow_owner_runtime_step_with_controller(r,r->gate,advance_power);}
#else
#define FINAL_CONNECTION 4
#define FINAL_INITIALIZED 1
static int tick(struct xnow_owner_runtime *r){return xnow_owner_runtime_step(r);}
#endif
struct data_context {struct xnow_full_control *control;int input,output,fail_close;unsigned closed,storage_checks;
#ifdef XNOW_TEST_MODE_ADMISSION
 struct wr_owner_admission *admission;struct xw_wireless_mode_policy *policy;
#endif
};
static int storage(void *p){struct data_context *d=p;d->storage_checks++;return 0;} /* Mocked PC ownership, not device proof. */
static int close_data(void *p){struct data_context *d=p;assert(xnow_full_control_finished(d->control)&&!clients&&connection==FINAL_CONNECTION);if(d->fail_close)return -1;
#ifdef XNOW_TEST_MODE_ADMISSION
 assert(d->policy->state.active&&wr_owner_admission_close(d->admission)>=0&&d->policy->state.active);
#endif
 assert(!close(d->input)&&!close(d->output));d->input=d->output=-1;d->closed++;return chdir("/");}
static void scenario(int fail_close,unsigned cause){
 (void)cause;
 reset();fixture_platform_reset();connection=4;clients=0;closes=0;
#ifdef XNOW_TEST_POWER_OFF
 connection=3;power_off_calls=0;
#endif
 int in[2],out[2],handoff[2];assert(!pipe(in)&&!pipe(out)&&!pipe(handoff));for(unsigned i=0;i<2;i++){nonblock(in[i]);nonblock(out[i]);}nonblock(handoff[0]);
 struct xnow_owner_gate gate;volatile int stop_requested=0;struct xnow_full_control controller;struct data_context data={.control=&controller,.input=in[0],.output=out[1],.fail_close=fail_close};
#ifdef XNOW_TEST_MODE_ADMISSION
 struct xw_wireless_mode_policy policy={0};struct xw_wireless_lease lease;
 struct xw_mode_channel view={0};struct wr_owner_admission admission={0};int mode_pair[2];
 assert(!xw_mode_policy_init(&policy,811)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_ESPNOW,1));
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x123,&lease));
 assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,mode_pair));
 assert(!xw_mode_channel_open(&view,&policy,mode_pair[0],lease.consumer,XW_MODE_GRANT_READ));close(mode_pair[0]);
 assert(!xw_mode_channel_observe(&view,&lease)&&!wr_owner_admission_open(&admission,mode_pair[1],&lease));close(mode_pair[1]);
 int permit=wr_owner_admission_poll(&admission,1000);
 for(unsigned i=0;permit==XW_MODE_PENDING;i++){
  assert(i<10);int rc=xw_mode_channel_step(&view);assert(rc==0||rc==XW_MODE_PENDING);
  permit=wr_owner_admission_poll(&admission,1001+i);
 }
 assert(!permit&&wr_owner_admission_allowed(&admission));data.admission=&admission;data.policy=&policy;
#endif
 assert(!xnow_owner_gate_open(&gate,in[0],&stop_requested,&data,storage));
 struct xnow_full_fingerprint range={0x8078,4,{0}};struct xnow_full_profile profile={layout,1,&range};struct xnow_full_control_options options={&gate,&profile,guard,guard,xnow_owner_gate_radio_valid,random4,8,1,0};
#ifdef XNOW_TEST_POWER_OFF
 options.allow_disconnect=0;
#endif
 assert(!xnow_full_control_init(&controller,&options));
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_control(&commands,&controller));struct xnow_owner_stream stream;assert(!xnow_owner_stream_open(&stream,&commands,in[0],out[1]));
 uint8_t cookie[16]={1,2,3,4,5,6,7,8};struct xnow_owner_runtime runtime;
 struct xnow_owner_runtime refused;controller.options.encrypted_limit=17;
 assert(xnow_owner_runtime_init(&refused,&controller,&gate,&stream,&commands,handoff[1],cookie,&data,0,close_data)==XNOW_ARGUMENT);controller.options.encrypted_limit=0;
 assert(xnow_owner_runtime_init(&refused,&controller,&gate,&stream,&commands,out[1],cookie,&data,0,close_data)==XNOW_IDENTITY);assert(!clients&&!fixture_jobs);
 assert(!xnow_owner_runtime_init(&runtime,&controller,&gate,&stream,&commands,handoff[1],cookie,&data,0,close_data));
 for(unsigned i=0;!runtime.prepared;i++){assert(i<200&&tick(&runtime)==XNOW_PENDING);}assert(data.storage_checks&&clients&&connection==3);
 uint8_t cmd[XNOW_OWNER_COMMAND_MAX],address[6]={2,1,2,3,4,5};size_t n=request(cmd,XNOW_OWNER_ADD,1,26);memcpy(cmd+16,address,6);cmd[22]=8;cmd[23]=2;command(&stream,in[1],out[0],cmd,n);
 n=request(cmd,XNOW_OWNER_SEND,2,1476);memcpy(cmd+16,address,6);memset(cmd+22,0x57,1470);command(&stream,in[1],out[0],cmd,n);
 assert(tick(&runtime)==XNOW_PENDING&&controller.backend.inflight);
 unsigned jobs=fixture_jobs,closed=closes;
#ifdef XNOW_TEST_MODE_ADMISSION
 if(cause){
  uint64_t stamp=admission.observed_at;
  if(cause==1){
   assert(xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
   permit=wr_owner_admission_poll(&admission,stamp+200);
   for(unsigned i=0;permit==XW_MODE_PENDING;i++){
    assert(i<10);int rc=xw_mode_channel_step(&view);assert(rc==0||rc==XW_MODE_PENDING);
    permit=wr_owner_admission_poll(&admission,stamp+201+i);
   }
   assert(permit==XW_MODE_DENIED);
  }else{
   assert(wr_owner_admission_poll(&admission,stamp+200)==XW_MODE_PENDING);
   permit=wr_owner_admission_poll(&admission,stamp+1000);assert(permit==XW_MODE_FAULT);
  }
  assert(!wr_owner_admission_allowed(&admission)&&policy.state.active&&xnow_owner_gate_radio_valid(&gate));
  stop_requested=permit<0;
 }else
#endif
 {close(in[1]);in[1]=-1;}
 for(unsigned i=0;i<5;i++)assert(tick(&runtime)==XNOW_PENDING&&controller.stop_requested&&clients&&controller.radio.fd==123&&fixture_jobs==jobs&&closes==closed&&!data.closed);
 uint8_t record[33];assert(read(handoff[0],record,sizeof record)<0&&errno==EAGAIN);
 done(0);int result=XNOW_PENDING;for(unsigned i=0;result==XNOW_PENDING;i++){assert(i<200);result=tick(&runtime);}
 assert(xnow_full_control_finished(&controller)&&!clients&&connection==FINAL_CONNECTION&&fixture_radio_kind==0&&fixture_initialized==FINAL_INITIALIZED);
#ifdef XNOW_TEST_POWER_OFF
 assert(power_off_calls==1);
#endif
 if(fail_close){
  assert(result==XNOW_UNCERTAIN&&runtime.fault&&!runtime.done&&!data.closed&&gate.socket_fd>=0);assert(tick(&runtime)==XNOW_UNCERTAIN);assert(read(handoff[0],record,sizeof record)<0&&errno==EAGAIN);
  /* Explicit PC fixture cleanup, not runtime recovery or fabricated DONE. */
  assert(!xnow_owner_stream_close(&stream)&&!xnow_owner_gate_release(&gate,&controller));close(in[0]);close(out[1]);close(handoff[1]);
 }else{
  assert(!result&&runtime.done&&runtime.writer==-1&&data.closed==1&&runtime.released&&gate.socket_fd==-1);
  assert(read(handoff[0],record,sizeof record)==32&&!memcmp(record,"XRFDONE1",8)&&!memcmp(record+8,cookie,16)&&record[24]==1);assert(read(handoff[0],record,sizeof record)==0);
  for(unsigned i=0;i<sizeof runtime.cookie;i++)assert(!runtime.cookie[i]);
 }
 close(out[0]);close(handoff[0]);
#ifdef XNOW_TEST_MODE_ADMISSION
 assert(policy.state.active); /* Only the parent consumes the retirement proof. */
 if(admission.client.bound)assert(wr_owner_admission_close(&admission)>=0);
 assert(!xw_mode_channel_close(&view));
 int mode_stop=xw_mode_policy_quiesce(&policy,&lease);assert(mode_stop==0||mode_stop==XW_MODE_PENDING);
 assert(!xw_mode_policy_release(&policy,&lease,1));
#endif
 if(in[1]>=0)close(in[1]);
}
int main(void){assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);scenario(0,0);scenario(1,0);
#ifdef XNOW_TEST_MODE_ADMISSION
 scenario(0,1);scenario(1,1);scenario(0,2);puts("MODE_REVOKE_RETIREMENT_PASS");
#endif
 puts("Managed full-owner runtime: actual gate/controller/IPC, inflight UI disconnect, restore before cleanup/token, DONE+EOF, cleanup failure retained without notification; stock hardware effects mocked.");return 0;}
