/* ARM-guest radio model. No device/driver APIs: exercise actual service IPC. */
#include "../../runtime/apps/wireless-remote/control.h"
#include "../../runtime/apps/wireless-remote/pairing_proof.h"
#include "../../runtime/apps/wireless-remote/pairing_auto.h"
#include "../../runtime/apps/wireless-remote/mode_wire.h"
#include "../../runtime/apps/wireless-remote/run_profile.h"
#include "../../runtime/store/deadline.h"
#include <assert.h>
#include <fcntl.h>
#include "../../runtime/platform/player/wireless_host.h"
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
#include <stdio.h>
#include <unistd.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
#ifdef WR_CHAIN_ARTWORK
#include "../../runtime/apps/wireless-remote/artwork_client.h"
#include "artwork_test_payload.h"
static struct wr_artwork_client artwork_client;
static unsigned artwork_finished,artwork_command_started;
#endif
#ifdef WR_CHAIN_OWNER_VIEW
#include "../../runtime/apps/wireless-remote/owner_admission.h"
#include "../../runtime/platform/espnow/xnow_endpoint.h"
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
static void deadline(void){unsigned long long now;assert(!hb_monotonic_millis(&now)&&now>=began&&now-began<
#ifdef WR_CHAIN_ARTWORK
 20000
#else
 8000
#endif
 );}
static void send_all(int fd,const void *data,size_t bytes){const uint8_t *p=data;while(bytes){deadline();ssize_t n=write(fd,p,bytes);if(n<0&&(errno==EAGAIN||errno==EINTR)){struct pollfd f={fd,POLLOUT,0};poll(&f,1,10);continue;}assert(n>0);p+=n;bytes-=(size_t)n;}}
#ifdef WR_CHAIN_DEVICE_PAIRING
static void read_all(int fd,uint8_t *data,size_t bytes){
 while(bytes){
  deadline();ssize_t n=read(fd,data,bytes);
  if(n<0&&(errno==EAGAIN||errno==EINTR)){poll(0,0,1);continue;}
  assert(n>0);data+=n;bytes-=(size_t)n;
 }
}
#endif
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
#ifdef WR_CHAIN_ARTWORK
static uint64_t artwork_now(void){unsigned long long now;assert(!hb_monotonic_millis(&now)&&now>=began);return now-began+100;}
static void artwork_tick(int output,unsigned ready){
 if(!ready||artwork_finished)return;
 uint64_t now=artwork_now();wr_artwork_client_tick(&artwork_client,now);
 const struct wr_artwork_progress *progress=wr_artwork_client_progress(&artwork_client);
 assert(!progress->failed);
 uint8_t packet[32+WR_ARTWORK_REQUEST_BYTES]={0};
 if(wr_artwork_client_request(&artwork_client,now,packet+32,WR_ARTWORK_REQUEST_BYTES,key))return;
 memcpy(packet,"XNR1",4);put(packet+4,sizeof packet);memcpy(packet+12,peer,6);
 packet[18]=2;packet[19]=1;memcpy(packet+20,"1234",4);put(packet+24,2);
 send_all(output,packet,sizeof packet);
}
#endif
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
 int view=fdnum(argv[10]);
#ifdef WR_CHAIN_SHARED_WIFI
#ifdef WR_CHAIN_DEVICE_PAIRING
 if(!strcmp(argv[9],"--pairing-view")){
  assert(!strcmp(argv[6],"000000000000")&&number64(argv[13])==XW_NATIVE_WIFI_CONSUMER);
  assert(fixture_fcntl(input,F_GETFD)>=0&&fixture_fcntl(output,F_GETFD)>=0&&fixture_fcntl(writer,F_GETFD)>=0&&fixture_fcntl(view,F_GETFD)>=0);
#ifdef WR_CHAIN_DELAYED_PAIRING_READY
  poll(0,0,300); /* Real IPC startup gap, with no RF or device operations. */
#endif
  uint8_t ready[
#ifdef WR_CHAIN_DIAGNOSTIC_READY
   75
#else
   37
#endif
  ]={0},invite[32+WR_PAIR_AUTO_INVITE_BYTES]={0};
  memcpy(ready,"XNR1",4);put(ready+4,sizeof ready);ready[12]=2;ready[17]=1;
  ready[18]=1;ready[19]=1;memcpy(ready+32,"WPL1",4);ready[36]=11;
#ifdef WR_CHAIN_DIAGNOSTIC_READY
  memcpy(ready+32,"WPL3",4);ready[46]=7;put(ready+71,1234);
#endif
  memcpy(invite,"XNR1",4);put(invite+4,sizeof invite);invite[12]=2;invite[17]=2;
  uint8_t private_key[32]={7},public_key[32],controller_nonce[16]={3};
  assert(!wr_pair_curve_public(public_key,private_key));
  invite[18]=1;invite[19]=1;put(invite+24,1);
  assert(!wr_pair_auto_invite(invite+32,11,controller_nonce,public_key));
  send_all(output,ready,sizeof ready);send_all(output,invite,sizeof invite);
#ifdef WR_CHAIN_DEVICE_PAIRING
  uint8_t request[22+WR_PAIR_AUTO_OFFER_BYTES];
  read_all(input,request,sizeof request);
  assert(!memcmp(request,"XNC1",4)&&request[4]==4&&!request[5]&&get(request+12)==6+WR_PAIR_AUTO_OFFER_BYTES);
  assert(!memcmp(request+16,"\xff\xff\xff\xff\xff\xff",6));
  struct wr_pairing_transcript transcript={{2,0,0,0,0,1},{2,0,0,0,0,2},{4},{3}};
  uint8_t secret[16];memcpy(transcript.walkman_nonce,request+26,16);
  struct wr_pairing_keys keys;
  assert(!wr_pair_auto_offer_read(&keys,secret,request+22,private_key,public_key,&transcript));
  uint8_t ack[16]={0},tx[32]={0},reply[32+WR_PAIRING_CONFIRM_BYTES]={0};
  memcpy(ack,"XNA1",4);put(ack+4,get(request+8));put(ack+12,4);
  memcpy(tx,"XNT1",4);put(tx+4,sizeof tx);put(tx+8,get(request+8));memset(tx+16,255,6);
  memcpy(reply,"XNR1",4);put(reply+4,sizeof reply);memcpy(reply+12,transcript.controller,6);
  reply[18]=1;reply[19]=1;put(reply+24,1);
  assert(!wr_pair_auto_reply(reply+32,secret,&transcript));
  send_all(output,ack,sizeof ack);send_all(output,tx,sizeof tx);
  reply[32+36]^=1;send_all(output,reply,sizeof reply);
  reply[32+36]^=1;send_all(output,reply,sizeof reply);
  uint8_t stage[16+WR_PAIRING_RECORD_BYTES],radio[32];
  read_all(input,stage,sizeof stage);
  assert(!memcmp(stage,"XNC1",4)&&stage[4]==6&&get(stage+12)==WR_PAIRING_RECORD_BYTES);
  assert(!wr_pairing_record_read(stage+16,transcript.controller,0,radio));
  assert(!memcmp(radio,keys.pmk,16)&&!memcmp(radio+16,keys.lmk,16));
  put(ack+4,get(stage+8));put(ack+12,6);send_all(output,ack,sizeof ack);
  read_all(input,request,22+WR_PAIRING_CONFIRM_BYTES);
  assert(request[4]==4&&!wr_pairing_commit_check(request+22,&keys,&transcript,WR_PAIRING_WALKMAN));
  put(ack+4,get(request+8));put(ack+12,4);send_all(output,ack,sizeof ack);
  uint32_t first_commit=get(request+8);
  put(tx+8,first_commit);put(tx+12,(uint32_t)-1);send_all(output,tx,sizeof tx);
  read_all(input,request,22+WR_PAIRING_CONFIRM_BYTES);
  assert(request[4]==4&&get(request+8)>first_commit&&
         !wr_pairing_commit_check(request+22,&keys,&transcript,WR_PAIRING_WALKMAN));
  assert(!wr_pairing_commit_encode(reply+32,&keys,&transcript,WR_PAIRING_CONTROLLER));
  send_all(output,reply,sizeof reply);
  put(ack+4,get(request+8));send_all(output,ack,sizeof ack);
  put(tx+8,get(request+8));put(tx+12,0);send_all(output,tx,sizeof tx);
  uint8_t publish[16];
  read_all(input,publish,sizeof publish);
  assert(!memcmp(publish,"XNC1",4)&&publish[4]==7&&!get(publish+12));
  put(ack+4,get(publish+8));put(ack+12,7);send_all(output,ack,sizeof ack);
#endif
  char byte;
  for(;;){
   deadline();ssize_t count=read(input,&byte,1);
   if(!count)break;
   assert(count<0&&(errno==EAGAIN||errno==EINTR));poll(0,0,1);
  }
  uint8_t receipt[32]={0};
  memcpy(receipt,"XRFDONE1",8);memcpy(receipt+8,cookie,16);receipt[24]=1;
  assert(write(writer,receipt,sizeof receipt)==sizeof receipt);
  return 0;
 }
#endif
 assert(!strcmp(argv[9],"--shared-wifi-view"));
 struct xw_wireless_lease lease={number64(argv[11]),number64(argv[12]),number64(argv[13]),XW_WIRELESS_MODE_WIFI};
 assert(view!=input&&view!=output&&view!=writer&&!wr_owner_admission_open_shared(&mode_admission,view,&lease));
#else
 assert(!strcmp(argv[9],"--mode-view"));
 struct xw_wireless_lease lease={number64(argv[11]),number64(argv[12]),number64(argv[13]),XW_WIRELESS_MODE_ESPNOW};
 assert(view!=input&&view!=output&&view!=writer&&!wr_owner_admission_open(&mode_admission,view,&lease));
#endif
 close(view);
 assert(!wr_owner_admission_refresh(&mode_admission));int admission=XW_MODE_PENDING;
 while(admission==XW_MODE_PENDING){deadline();admission=wr_owner_admission_step(&mode_admission);if(admission==XW_MODE_PENDING)poll(0,0,1);}
 assert(!admission&&wr_owner_admission_allowed(&mode_admission));puts("REMOTE_CHAIN_MODE_VIEW_PASS");
#endif
 puts("REMOTE_CHAIN_OWNER_STARTED");puts("REMOTE_RF_ENDPOINT_READY");fflush(stdout);
 uint8_t buffer[1510];size_t used=0;unsigned statuses=0,receipts=0,paused=0;
#ifdef WR_CHAIN_MANUAL_STOP
 while(1){
#else
 while(!(statuses>=2&&receipts==2&&paused)){
#endif
  deadline();
#ifdef WR_CHAIN_ARTWORK
  artwork_tick(output,statuses);
  if(artwork_finished&&!artwork_command_started){artwork_command_started=1;command(output);}
#endif
  ssize_t n=read(input,buffer+used,sizeof buffer-used);
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
   int control_reply=0;
   int is_status=wr_status_frame(payload,size);
   if(is_status){struct wr_status s;assert(!wr_status_verify(&s,payload,size,key));
#ifdef WR_CHAIN_DYNAMIC_SESSION
    if(!run_session){assert(s.session&&s.session!=1234567);run_session=s.session;printf("REMOTE_CHAIN_SESSION=%llu\n",(unsigned long long)run_session);fflush(stdout);}
#endif
#ifdef WR_CHAIN_BROKER_MODEL
    assert(s.session==run_session&&(s.valid&35)==35&&s.volume==12);
    if(s.valid&4){assert(!strncmp(s.title,"Song ",5));statuses++;}
#else
    assert(s.session==run_session&&(s.valid&39)==39&&!strcmp(s.title,"Channel song")&&s.volume==12);statuses++;
#endif
    if(s.state==XW_PLAY_PAUSED)paused=1;
#ifdef WR_CHAIN_ARTWORK
    if(!artwork_finished)wr_artwork_client_observe(&artwork_client,&s,1,artwork_now());
#endif
   }
   else if(size==WR_MODE_BYTES&&!memcmp(payload,"WRM1",4)){
    struct wr_mode mode;assert(!wr_mode_decode(&mode,payload,size,key)&&(!run_session||mode.session==run_session));
   }else if(size==WR_HEARTBEAT_BYTES){uint64_t session;uint32_t sequence,snapshot;assert(!wr_heartbeat_verify(&session,&sequence,&snapshot,payload,size,key)&&session==run_session);}
#ifdef WR_CHAIN_ARTWORK
   else if(size>=WR_ARTWORK_REPLY_HEADER_BYTES&&size<=WR_ARTWORK_REPLY_MAX&&!memcmp(payload,"WRAR",4)){
    assert(!wr_artwork_client_accept(&artwork_client,artwork_now(),payload,size,key));
    if(wr_artwork_client_image_ready(&artwork_client)){
     const struct wr_artwork_progress *progress=wr_artwork_client_progress(&artwork_client);
     assert(progress->total==sizeof wr_chain_artwork_data&&!memcmp(artwork_client.data,wr_chain_artwork_data,sizeof wr_chain_artwork_data));
     artwork_finished=1;printf("REMOTE_CHAIN_ARTWORK_PASS bytes=%u\n",progress->total);fflush(stdout);
    }
   }
#endif
   else {struct wr_control_receipt r;assert(!wr_receipt_decode(&r,payload,size,key)&&r.session==run_session&&r.request==1&&r.result==XW_PLAYER_ACCEPTED);receipts++;control_reply=1;}
   uint8_t ack[16]={0};memcpy(ack,"XNA1",4);put(ack+4,request);put(ack+12,4);send_all(output,ack,sizeof ack);
   uint8_t complete[32]={0};memcpy(complete,"XNT1",4);put(complete+4,32);put(complete+8,request);memcpy(complete+16,peer,6);send_all(output,complete,sizeof complete);
#ifdef WR_CHAIN_ARTWORK
   if(control_reply&&receipts==1)command(output);
#else
   if((is_status&&statuses==1&&!receipts)||(control_reply&&receipts==1))command(output);
#endif
   memmove(buffer,buffer+16+bytes,used-16-bytes);used-=16+bytes;
  }
 }
 (void)paused;assert(!used);close(input);close(output);
#ifdef WR_CHAIN_OWNER_VIEW
 assert(wr_owner_admission_close(&mode_admission)>=0&&!wr_owner_admission_allowed(&mode_admission));
#endif
 uint8_t record[32]={0};memcpy(record,"XRFDONE1",8);memcpy(record+8,cookie,16);record[24]=1;
#ifdef WR_CHAIN_SHARED_WIFI
 put(record+28,(uint32_t)XNOW_ENDPOINT_CHANNEL);
#endif
 send_all(writer,record,sizeof record);close(writer);
 puts("REMOTE_CHAIN_OWNER_MODEL_PASS");return 0;
}
