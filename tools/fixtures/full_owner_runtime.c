#define FULL_OWNER_IPC_MAIN ipc_checks
#include "full_owner_ipc.c"
#include "../../runtime/platform/espnow/xnow_owner_runtime.h"
struct data_context {struct xnow_full_control *control;int input,output,fail_close;unsigned closed,storage_checks;};
static int storage(void *p){struct data_context *d=p;d->storage_checks++;return 0;} /* Mocked PC ownership, not device proof. */
static int close_data(void *p){struct data_context *d=p;assert(xnow_full_control_finished(d->control)&&!clients&&connection==4);if(d->fail_close)return -1;assert(!close(d->input)&&!close(d->output));d->input=d->output=-1;d->closed++;return chdir("/");}
static void scenario(int fail_close){
 reset();fixture_platform_reset();connection=4;clients=0;closes=0;
 int in[2],out[2],handoff[2];assert(!pipe(in)&&!pipe(out)&&!pipe(handoff));for(unsigned i=0;i<2;i++){nonblock(in[i]);nonblock(out[i]);}nonblock(handoff[0]);
 struct xnow_owner_gate gate;volatile int stop_requested=0;struct xnow_full_control controller;struct data_context data={&controller,in[0],out[1],fail_close,0,0};
 assert(!xnow_owner_gate_open(&gate,in[0],&stop_requested,&data,storage));
 struct xnow_full_fingerprint range={0x8078,4,{0}};struct xnow_full_profile profile={layout,1,&range};struct xnow_full_control_options options={&gate,&profile,guard,guard,xnow_owner_gate_radio_valid,random4,8,1,0};assert(!xnow_full_control_init(&controller,&options));
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_control(&commands,&controller));struct xnow_owner_stream stream;assert(!xnow_owner_stream_open(&stream,&commands,in[0],out[1]));
 uint8_t cookie[16]={1,2,3,4,5,6,7,8};struct xnow_owner_runtime runtime;
 struct xnow_owner_runtime refused;controller.options.encrypted_limit=17;
 assert(xnow_owner_runtime_init(&refused,&controller,&gate,&stream,&commands,handoff[1],cookie,&data,0,close_data)==XNOW_ARGUMENT);controller.options.encrypted_limit=0;
 assert(xnow_owner_runtime_init(&refused,&controller,&gate,&stream,&commands,out[1],cookie,&data,0,close_data)==XNOW_IDENTITY);assert(!clients&&!fixture_jobs);
 assert(!xnow_owner_runtime_init(&runtime,&controller,&gate,&stream,&commands,handoff[1],cookie,&data,0,close_data));
 for(unsigned i=0;!runtime.prepared;i++){assert(i<200&&xnow_owner_runtime_step(&runtime)==XNOW_PENDING);}assert(data.storage_checks&&clients&&connection==3);
 uint8_t cmd[XNOW_OWNER_COMMAND_MAX],address[6]={2,1,2,3,4,5};size_t n=request(cmd,XNOW_OWNER_ADD,1,26);memcpy(cmd+16,address,6);cmd[22]=8;cmd[23]=2;command(&stream,in[1],out[0],cmd,n);
 n=request(cmd,XNOW_OWNER_SEND,2,1476);memcpy(cmd+16,address,6);memset(cmd+22,0x57,1470);command(&stream,in[1],out[0],cmd,n);
 assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&controller.backend.inflight);
 unsigned jobs=fixture_jobs,closed=closes;close(in[1]);in[1]=-1;
 for(unsigned i=0;i<5;i++)assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&controller.stop_requested&&clients&&controller.radio.fd==123&&fixture_jobs==jobs&&closes==closed&&!data.closed);
 uint8_t record[33];assert(read(handoff[0],record,sizeof record)<0&&errno==EAGAIN);
 done(0);int result=XNOW_PENDING;for(unsigned i=0;result==XNOW_PENDING;i++){assert(i<200);result=xnow_owner_runtime_step(&runtime);}
 assert(xnow_full_control_finished(&controller)&&!clients&&connection==4&&fixture_radio_kind==0&&fixture_initialized);
 if(fail_close){
  assert(result==XNOW_UNCERTAIN&&runtime.fault&&!runtime.done&&!data.closed&&gate.socket_fd>=0);assert(xnow_owner_runtime_step(&runtime)==XNOW_UNCERTAIN);assert(read(handoff[0],record,sizeof record)<0&&errno==EAGAIN);
  /* Explicit PC fixture cleanup, not runtime recovery or fabricated DONE. */
  assert(!xnow_owner_stream_close(&stream)&&!xnow_owner_gate_release(&gate,&controller));close(in[0]);close(out[1]);close(handoff[1]);
 }else{
  assert(!result&&runtime.done&&runtime.writer==-1&&data.closed==1&&runtime.released&&gate.socket_fd==-1);
  assert(read(handoff[0],record,sizeof record)==32&&!memcmp(record,"XRFDONE1",8)&&!memcmp(record+8,cookie,16)&&record[24]==1);assert(read(handoff[0],record,sizeof record)==0);
  for(unsigned i=0;i<sizeof runtime.cookie;i++)assert(!runtime.cookie[i]);
 }
 close(out[0]);close(handoff[0]);
}
int main(void){assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);scenario(0);scenario(1);puts("Managed full-owner runtime: actual gate/controller/IPC, inflight UI disconnect, restore before cleanup/token, DONE+EOF, cleanup failure retained without notification; stock hardware effects mocked.");return 0;}
