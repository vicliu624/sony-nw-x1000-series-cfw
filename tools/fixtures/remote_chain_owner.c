/* ARM-guest radio model. No device/driver APIs: exercise actual service IPC. */
#include "../../runtime/apps/wireless-remote/control.h"
#include "../../runtime/store/deadline.h"
#include <assert.h>
#include <stdio.h>
#include <unistd.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
#ifdef WR_CHAIN_OWNER_VIEW
#include "../../runtime/apps/wireless-remote/owner_admission.h"
static struct wr_owner_admission mode_admission;
static uint64_t number64(const char *p){uint64_t n=0;assert(p&&*p);for(;*p;p++){assert(*p>='0'&&*p<='9'&&n<=(UINT64_MAX-(unsigned)(*p-'0'))/10);n=n*10+(unsigned)(*p-'0');}assert(n);return n;}
#endif
static const uint8_t peer[6]={2,1,2,3,4,5};
#ifdef WR_CHAIN_DYNAMIC_SESSION
static uint64_t run_session;
#else
static uint64_t run_session=1234567;
#endif
static uint8_t key[32];static unsigned long long began;
static uint32_t get(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static int digit(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
static int fdnum(const char *s){int n=0;while(*s){assert(*s>='0'&&*s<='9');n=n*10+*s++-'0';assert(n<65536);}assert(n>=3);return n;}
static void deadline(void){unsigned long long now;assert(!hb_monotonic_millis(&now)&&now>=began&&now-began<8000);}
static void send_all(int fd,const void *data,size_t bytes){const uint8_t *p=data;while(bytes){deadline();ssize_t n=write(fd,p,bytes);if(n<0&&(errno==EAGAIN||errno==EINTR)){struct pollfd f={fd,POLLOUT,0};poll(&f,1,10);continue;}assert(n>0);p+=n;bytes-=(size_t)n;}}
static void command(int output){
 uint8_t packet[32+WR_CONTROL_BYTES]={0};memcpy(packet,"XNR1",4);put(packet+4,sizeof packet);memcpy(packet+12,peer,6);packet[18]=2;packet[19]=1;memcpy(packet+20,"1234",4);put(packet+24,2);
 struct wr_control c={run_session,1,
#ifdef WR_CHAIN_BROKER_MODEL
 XW_OP_NEXT,
#else
 XW_OP_PAUSE,
#endif
 0};assert(!wr_control_encode(packet+32,WR_CONTROL_BYTES,&c,key));send_all(output,packet,sizeof packet);
}
int main(int argc,char **argv){
 assert(argc==
#ifdef WR_CHAIN_OWNER_VIEW
 14
#else
 9
#endif
 &&!strcmp(argv[1],"--owner"));int input=fdnum(argv[2]),output=fdnum(argv[3]),writer=fdnum(argv[4]);
 uint8_t cookie[16];assert(strlen(argv[5])==32);for(unsigned i=0;i<16;i++){int a=digit(argv[5][2*i]),b=digit(argv[5][2*i+1]);assert(a>=0&&b>=0);cookie[i]=(uint8_t)(a*16+b);}
 for(unsigned i=0;i<32;i++)key[i]=(uint8_t)(i+1);assert(!hb_monotonic_millis(&began));
#ifdef WR_CHAIN_OWNER_VIEW
 assert(!strcmp(argv[9],"--mode-view"));int view=fdnum(argv[10]);
 struct xw_wireless_lease lease={number64(argv[11]),number64(argv[12]),number64(argv[13]),XW_WIRELESS_MODE_ESPNOW};
 assert(view!=input&&view!=output&&view!=writer&&!wr_owner_admission_open(&mode_admission,view,&lease));close(view);
 assert(!wr_owner_admission_refresh(&mode_admission));int admission=XW_MODE_PENDING;
 while(admission==XW_MODE_PENDING){deadline();admission=wr_owner_admission_step(&mode_admission);if(admission==XW_MODE_PENDING)poll(0,0,1);}
 assert(!admission&&wr_owner_admission_allowed(&mode_admission));puts("REMOTE_CHAIN_MODE_VIEW_PASS");
#endif
 puts("REMOTE_CHAIN_OWNER_STARTED");fflush(stdout);
 uint8_t buffer[1510];size_t used=0;unsigned statuses=0,receipts=0,paused=0;
#ifdef WR_CHAIN_MANUAL_STOP
 while(1){
#else
 while(!(statuses>=2&&receipts==2&&paused)){
#endif
  deadline();ssize_t n=read(input,buffer+used,sizeof buffer-used);
  if(n<0&&(errno==EINTR||errno==EAGAIN)){struct pollfd f={input,POLLIN,0};poll(&f,1,10);continue;}
#ifdef WR_CHAIN_MANUAL_STOP
  if(!n){
#ifndef WR_CHAIN_ALLOW_EMPTY_STOP
   assert(statuses>=1);
#endif
   break;}
#endif
  assert(n>0);used+=(size_t)n;
  while(used>=16){assert(!memcmp(buffer,"XNC1",4)&&buffer[4]==4&&!buffer[5]&&!buffer[6]&&!buffer[7]);
   uint32_t request=get(buffer+8),bytes=get(buffer+12);assert(request&&bytes>=6&&bytes<=1476);if(used<16+bytes)break;
   assert(!memcmp(buffer+16,peer,6));const uint8_t *payload=buffer+22;size_t size=bytes-6;
   if(size==WR_SIGNED_STATUS_BYTES){struct wr_status s;assert(!wr_status_verify(&s,payload,size,key));
#ifdef WR_CHAIN_DYNAMIC_SESSION
    if(!run_session){assert(s.session&&s.session!=1234567);run_session=s.session;printf("REMOTE_CHAIN_SESSION=%llu\n",(unsigned long long)run_session);fflush(stdout);}
#endif
#ifdef WR_CHAIN_BROKER_MODEL
    assert(s.session==run_session&&(s.valid&35)==35&&s.volume==12);
    if(s.valid&4){assert(!strncmp(s.title,"Song ",5));statuses++;}
#else
    assert(s.session==run_session&&(s.valid&39)==39&&!strcmp(s.title,"Channel song")&&s.volume==12);statuses++;
#endif
    if(s.state==XW_PLAY_PAUSED)paused=1;}
   else {struct wr_control_receipt r;assert(!wr_receipt_decode(&r,payload,size,key)&&r.session==run_session&&r.request==1&&r.result==XW_PLAYER_ACCEPTED);receipts++;}
   uint8_t ack[16]={0};memcpy(ack,"XNA1",4);put(ack+4,request);put(ack+12,4);send_all(output,ack,sizeof ack);
   uint8_t complete[32]={0};memcpy(complete,"XNT1",4);put(complete+4,32);put(complete+8,request);memcpy(complete+16,peer,6);send_all(output,complete,sizeof complete);
   if((statuses==1&&!receipts)||(size==WR_CONTROL_BYTES&&receipts==1))command(output);
   memmove(buffer,buffer+16+bytes,used-16-bytes);used-=16+bytes;
  }
 }
 (void)paused;assert(!used);close(input);close(output);
#ifdef WR_CHAIN_OWNER_VIEW
 assert(wr_owner_admission_close(&mode_admission)>=0&&!wr_owner_admission_allowed(&mode_admission));
#endif
 uint8_t record[32]={0};memcpy(record,"XRFDONE1",8);memcpy(record+8,cookie,16);record[24]=1;send_all(writer,record,sizeof record);close(writer);
 puts("REMOTE_CHAIN_OWNER_MODEL_PASS");return 0;
}
