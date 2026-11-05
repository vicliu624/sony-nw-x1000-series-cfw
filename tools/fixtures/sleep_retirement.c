#include "../../runtime/platform/player/sleep_retirement.h"
static unsigned long thread=17;
unsigned long pthread_self(void){return thread;}
static struct xw_sleep_retirement gate;
static unsigned radio_wait,sdk_wait,acks,quiesced,valid_calls,fail_valid,radio_fail;
static int valid(void *p,uint64_t epoch){
 if(p!=&gate||epoch!=41)return XW_PLAYER_STALE;
 valid_calls++;return fail_valid&&valid_calls>=fail_valid?XW_PLAYER_STALE:0;
}
static int quiesce(void *p){(void)p;quiesced++;return 0;}
static int radio(void *p,uint64_t epoch){
 (void)p;(void)epoch;if(!quiesced)return XW_PLAYER_PROTOCOL;
 if(radio_wait){radio_wait--;return XW_PLAYER_ACCEPTED;}
 return radio_fail?XW_PLAYER_UNCERTAIN:0;
}
static int stop(void *p){(void)p;if(sdk_wait){sdk_wait--;return XW_PLAYER_BUSY;}return 0;}
static int ack(void *p){
 (void)p;if(radio_wait||sdk_wait||!quiesced)return XW_PLAYER_PROTOCOL;
 if(xw_sleep_retirement_poll(&gate)!=XW_PLAYER_BUSY)return XW_PLAYER_PROTOCOL;
 acks++;return 0;
}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
static int run(void){
 static const struct xw_sleep_retirement_ops ops={valid,quiesce,radio,stop,ack};
 for(unsigned scenario=0;scenario<5;scenario++){
  struct xw_sleep_retirement empty={0};gate=empty;
  radio_wait=2;sdk_wait=2;acks=quiesced=valid_calls=fail_valid=radio_fail=0;thread=17;
  CHECK(xw_sleep_retirement_begin(&gate,&ops,&gate,41,17)==XW_PLAYER_ACCEPTED);
  CHECK(!acks&&quiesced==1);
  CHECK(xw_sleep_retirement_begin(&gate,&ops,&gate,42,17)==XW_PLAYER_BUSY);
  if(scenario==1){thread=18;CHECK(xw_sleep_retirement_poll(&gate)==XW_PLAYER_BUSY);thread=17;}
  if(scenario==2)fail_valid=2;
  if(scenario==3)radio_fail=1;
  if(scenario==4)fail_valid=7; /* last validation, after radio and SDK drain */
  int rc=XW_PLAYER_ACCEPTED;
  for(unsigned i=0;i<12&&rc==XW_PLAYER_ACCEPTED;i++){
   rc=xw_sleep_retirement_poll(&gate);
   if(rc==XW_PLAYER_ACCEPTED)CHECK(!acks);
  }
  if(scenario>=2){CHECK(rc<0&&!acks&&gate.phase==XW_SLEEP_FAILED);CHECK(xw_sleep_retirement_poll(&gate)==rc);}
  else{CHECK(rc==0&&acks==1&&gate.phase==XW_SLEEP_ACKNOWLEDGED);CHECK(!xw_sleep_retirement_poll(&gate)&&acks==1);}
 }
 return 0;
}
#ifdef ARM_FIXTURE
void *memset(void *target,int value,unsigned bytes){unsigned char *p=target;for(unsigned i=0;i<bytes;i++)p[i]=(unsigned char)value;return target;}
void _start(void){int result=run();__asm__ volatile("mov r0,%0\n\tswi 0x900001"::"r"(result):"r0","memory");for(;;){}}
#else
int main(void){return run();}
#endif
