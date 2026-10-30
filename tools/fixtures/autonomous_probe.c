/* Real full controller/endpoint/backend; synthetic words and original effects. */
#define FULL_OWNER_IPC_MAIN unused_ipc_checks
#include "full_owner_ipc.c"
#include "../../runtime/apps/espnow-test/runner.h"
static unsigned events,frames;static int fail_log,done_result;
static int log_event(void *unused,const char *name,int value){(void)unused;events++;if(!strcmp(name,"done"))done_result=value;return fail_log?-1:0;}
static int log_frame(void *unused,const uint8_t *data,size_t n){(void)unused;assert(n>=39&&data[0]==0xd0);frames++;return fail_log?-1:0;}
static void begin(struct xnow_full_control *c,struct probe_run *run,unsigned tx){
 reset();fixture_platform_reset();clients=0;connection=4;lease_valid=1;closes=events=frames=0;fail_log=0;done_result=-1;
 static struct xnow_full_fingerprint range={0x8078,4,{0}};static struct xnow_full_profile p;p.layout=layout;p.count=1;p.ranges=&range;
 struct xnow_full_control_options options={0,&p,guard,guard,valid,random4,8,1,0};assert(!xnow_full_control_init(c,&options));
 struct probe_log log={0,log_event,log_frame};uint8_t peer[6]={2,0x66,0x77,0x88,0x99,0xaa};assert(!probe_init(run,c,&log,peer,tx,1));
}
int main(void){
 struct xnow_full_control c;struct probe_run run;begin(&c,&run,1);int result=0;unsigned verified=0;uint32_t now=100;
 for(unsigned i=0;result==PROBE_RUNNING;i++,now+=10){assert(i<400);result=probe_step(&run,now,0);
  if(c.backend.inflight){uint8_t data[1470];struct xnow_wire_info info;assert(!xnow_espnow_decode_body((uint8_t *)packet+32,*at(layout.tx+20),data,sizeof data,&info));
   static const unsigned expected[]={0,1,249,250,0,1,250,251,1469,1470};assert(verified<10&&info.payload_bytes==expected[verified]&&info.version==(verified<4?1:2));for(unsigned j=0;j<info.payload_bytes;j++)assert(data[j]==(uint8_t)(j*17u+verified));verified++;done(0);}
 }
 assert(result==PROBE_DONE&&verified==10&&!run.failure&&done_result==0&&!clients&&connection==4&&fixture_radio_kind==0&&fixture_initialized);
 begin(&c,&run,0);result=0;now=100;int injected=0;
 for(unsigned i=0;result==PROBE_RUNNING;i++,now+=10){assert(i<400);result=probe_step(&run,now,0);
  if(run.ready&&injected<2){if(!injected){uint8_t data[12]={1};receive(data,sizeof data);}else{uint8_t protected[31]={1,0,0,0x20};memcpy(packet,protected,sizeof protected);uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;*at(slot)=PACKET;*at(slot+4)=sizeof protected;*at(slot+8)=0x88776602;*at(slot+12)=0x0001aa99;*at(layout.rx+4)=tail+1;}injected++;}}
 assert(result==PROBE_DONE&&frames==1&&run.received==2&&done_result==0&&!clients&&connection==4);
 begin(&c,&run,1);fail_log=1;assert(probe_step(&run,100,0)==PROBE_DONE&&!fixture_jobs&&!clients&&!allocations);
 begin(&c,&run,1);now=100;while(!c.backend.inflight){assert(now<1000);assert(probe_step(&run,now,0)==PROBE_RUNNING);now+=10;}
 unsigned jobs=fixture_jobs;for(unsigned i=0;i<5;i++)assert(probe_step(&run,2000+i,0)==PROBE_RUNNING&&fixture_jobs==jobs&&clients&&c.endpoint_ready);
 done(0);result=0;for(unsigned i=0;result==PROBE_RUNNING;i++){assert(i<200);result=probe_step(&run,2100+i,0);}
 assert(result==PROBE_DONE&&run.failure&&connection==4&&!clients&&fixture_radio_kind==0);
 begin(&c,&run,0);now=100;while(!run.ready){assert(probe_step(&run,now,0)==PROBE_RUNNING);now+=10;}
 fixture_stock_bad=1;result=0;for(unsigned i=0;result==PROBE_RUNNING;i++){assert(i<200);result=probe_step(&run,2000+i,0);}
 assert(result==PROBE_REPAIR&&clients&&!xnow_full_control_finished(&c));
 puts("Autonomous probe:10 binary v1/v2 cases, RX capture/window, initial journal refusal, in-flight deadline drain, stock reconnection and repair retention passed; RF effects modeled.");return 0;
}
