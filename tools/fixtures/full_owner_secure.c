#define FULL_OWNER_IPC_MAIN unused_ipc_checks
#include "full_owner_ipc.c"
#include "../../runtime/platform/espnow/xnow_owner_runtime.h"
#include "../../runtime/platform/espnow/xnow_endpoint_security.h"
#include "../../runtime/platform/espnow/xnow_pn_file.h"
#include <sys/stat.h>
#include "../../runtime/store/target_abi.h"
static const uint8_t local[6]={2,2,2,2,2,2},remote[6]={2,1,2,3,4,5},key[16]={0x16};
static struct xnow_endpoint_security workspace;
static uint8_t previous_frame[1560];static size_t previous_bytes;
static int read_failed;
static int transport_read(void *p,uint32_t address,uint32_t *out){return read_failed?-1:rd(p,address,out);}
struct security_data {struct xnow_full_control *control;struct xnow_owner_gate *gate;struct xnow_pn_file file;int input,output,mode;};
static int directory_guard(void *p){(void)p;return 0;} /* Explicit PC fixture only. */
static void fresh(struct xnow_pn_file *file,const uint8_t a[6],const uint8_t b[6]){
 struct xnow_pn tx;uint8_t rx[32];assert(!xnow_pn_init(&tx,a,key,1024,file,xnow_pn_file_reserve));assert(!xnow_pn_file_provision(file,tx.scope));assert(!xnow_security_rx_scope(rx,a,b,key));assert(!xnow_pn_file_provision(file,rx));xnow_pn_clear(&tx);
}
static int prepare(void *p,struct xnow_endpoint *e,const uint8_t actual[6]){
 struct security_data *d=p;if(d->mode==2)return 0; /* Inert callback must be refused. */
 assert(!memcmp(actual,local,6));struct xnow_security_io io={&d->file,xnow_pn_file_reserve,xnow_pn_file_load_rx,xnow_pn_file_commit_rx};
 int r=xnow_endpoint_security_attach(e,&workspace,actual,1024,&io);if(r)return r;
 struct xnow_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,remote,6);memcpy(peer.lmk,key,16);peer.version=2;peer.encrypt=1;
 r=xnow_endpoint_add(e,&peer);if(!r)r=e->crypto.prepare(e->crypto.context,&peer);memset(&peer,0,sizeof peer);if(r)return r;
 /* Check existing TX scope too; never provision/reset as part of startup. */
 struct xnow_pn tx;uint64_t high;assert(!xnow_pn_init(&tx,actual,key,1024,&d->file,xnow_pn_file_reserve));r=xnow_pn_file_load_rx(&d->file,tx.scope,&high);xnow_pn_clear(&tx);return r?XNOW_SECURITY_STORAGE:0;
}
static int cleanup(void *p){struct security_data *d=p;assert(xnow_full_control_finished(d->control)&&!clients&&connection==4);if(close(d->input)||close(d->output)||close(d->file.directory))return -1;d->file.directory=-1;return chdir("/");}
static void incoming(const uint8_t *frame,size_t bytes){memcpy(packet,frame+24,bytes-24);uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;*at(slot)=PACKET;*at(slot+4)=(uint32_t)(bytes-24);*at(slot+8)=0x03020102;*at(slot+12)=0x00010504;*at(layout.rx+4)=tail+1;}
static void unknown_plain(const uint8_t *frame,size_t bytes){memcpy(packet,frame+24,bytes-24);uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;*at(slot)=PACKET;*at(slot+4)=(uint32_t)(bytes-24);*at(slot+8)=0x07080902;*at(slot+12)=0x0506;*at(layout.rx+4)=tail+1;}
static void read_event(struct xnow_owner_runtime *r,int fd,uint8_t *out,size_t n){size_t used=0;for(unsigned i=0;used<n;i++){assert(i<100&&xnow_owner_runtime_step(r)==XNOW_PENDING);ssize_t k=read(fd,out+used,n-used);if(k<0){assert(errno==EAGAIN);continue;}assert(k>0);used+=(size_t)k;}}
static void run(const char *directory,int mode,unsigned expected){
 reset();fixture_platform_reset();clients=0;connection=4;
 int in[2],out[2],handoff[2];assert(!pipe(in)&&!pipe(out)&&!pipe(handoff));for(unsigned i=0;i<2;i++){nonblock(in[i]);nonblock(out[i]);}
 struct xnow_owner_gate gate;volatile int stop_requested=0;assert(!xnow_owner_gate_open(&gate,in[0],&stop_requested,0,directory_guard));
 int fd=open(directory,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);struct stat st;assert(fd>=0&&!fstat(fd,&st));
 struct xnow_full_control controller;struct security_data data={&controller,&gate,{fd,(uint64_t)st.st_dev,&gate,xnow_owner_gate_storage_guard},in[0],out[1],mode};
 struct xnow_full_fingerprint range={0x8078,4,{0}};struct xnow_full_profile profile={layout,1,&range};struct xnow_full_control_options options={&gate,&profile,guard,guard,xnow_owner_gate_radio_valid,random4,8,1,17};assert(!xnow_full_control_init(&controller,&options));
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_control(&commands,&controller));struct xnow_owner_stream stream;assert(!xnow_owner_stream_open(&stream,&commands,in[0],out[1]));uint8_t cookie[16]={1,2,3};struct xnow_owner_runtime runtime;
 assert(!xnow_owner_runtime_init(&runtime,&controller,&gate,&stream,&commands,handoff[1],cookie,&data,prepare,cleanup));
 for(unsigned i=0;!runtime.prepared&&!controller.stop_requested;i++){assert(i<200&&xnow_owner_runtime_step(&runtime)==XNOW_PENDING);}
 if(!mode){
  assert(runtime.prepared&&!runtime.application_failure);
  if(expected==1025){assert(previous_bytes);unsigned before=runtime.dropped;incoming(previous_frame,previous_bytes);assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&runtime.dropped==before+1&&!controller.stop_requested);}
  /* Plaintext from an unregistered sender is allowed, but malformed body is
   * a datagram rejection, never a driver/storage failure or owner teardown. */
  uint8_t bad_plain[80],small[16]={0},plain_random[4]={1,2,3,4},unknown[6]={2,9,8,7,6,5};size_t bad_bytes;
  assert(!xnow_espnow_encode_action(bad_plain,sizeof bad_plain,local,unknown,0,2,plain_random,small,sizeof small,&bad_bytes));
  for(unsigned broken=0;broken<2;broken++){
   bad_plain[37]=broken?4:5;bad_plain[38]=broken?7:2;
   unknown_plain(bad_plain,bad_bytes);
   unsigned rejected=runtime.dropped;assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING);
   assert(runtime.dropped==rejected+1&&!controller.stop_requested&&!stream.output_bytes&&!controller.backend.fault);
  }
  bad_plain[37]=4;bad_plain[38]=2;unknown_plain(bad_plain,bad_bytes);uint8_t plain_event[48];read_event(&runtime,out[0],plain_event,sizeof plain_event);assert(!memcmp(plain_event,"XNR1",4)&&!memcmp(plain_event+12,unknown,6)&&!memcmp(plain_event+32,small,sizeof small)&&!controller.stop_requested);
  uint8_t cmd[XNOW_OWNER_COMMAND_MAX];size_t n=request(cmd,XNOW_OWNER_SEND,91,1476);memcpy(cmd+16,remote,6);for(unsigned i=0;i<1470;i++)cmd[22+i]=(uint8_t)i;command(&stream,in[1],out[0],cmd,n);
  assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&controller.backend.inflight&&*at(layout.tx+16)==4);
  const uint8_t *iv=(const uint8_t *)packet+32;uint64_t pn=(uint64_t)iv[0]|(uint64_t)iv[1]<<8;for(unsigned i=0;i<4;i++)pn|=(uint64_t)iv[4+i]<<(16+8*i);assert(pn==expected);
  uint8_t frame[1560]={0xd0,0x40};memcpy(frame+4,remote,6);memcpy(frame+10,local,6);memset(frame+16,255,6);assert(*at(layout.tx+20)==1536);memcpy(frame+24,iv,1536);printf("TX %u ",expected);for(unsigned i=0;i<sizeof frame;i++)printf("%02x",frame[i]);puts("");
  done(0);uint8_t event[1502];read_event(&runtime,out[0],event,32);assert(!memcmp(event,"XNT1",4));
  struct xnow_security_io sio={&data.file,xnow_pn_file_reserve,xnow_pn_file_load_rx,xnow_pn_file_commit_rx};struct xnow_security sender;assert(!xnow_security_init(&sender,&sio,remote,local,key,0,1024));uint8_t payload[1470],random[4]={5,6,7,8};for(unsigned i=0;i<1470;i++)payload[i]=(uint8_t)(i*3);size_t bytes;assert(!xnow_security_seal(&sender,2,random,payload,sizeof payload,frame,sizeof frame,&bytes));
  frame[bytes-1]^=1;unsigned rejected=runtime.dropped;incoming(frame,bytes);assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&runtime.dropped==rejected+1&&!stream.output_bytes&&!controller.stop_requested);frame[bytes-1]^=1;
  incoming(frame,bytes);read_event(&runtime,out[0],event,sizeof event);assert(!memcmp(event,"XNR1",4)&&!memcmp(event+32,payload,1470));memcpy(previous_frame,frame,bytes);previous_bytes=bytes;
  unsigned before=runtime.dropped;incoming(frame,bytes);assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&runtime.dropped==before+1&&!controller.stop_requested);xnow_security_clear(&sender);
 }else if(mode==3){assert(runtime.prepared);read_failed=1;assert(xnow_owner_runtime_step(&runtime)==XNOW_PENDING&&controller.stop_requested&&runtime.application_failure==XNOW_IO);read_failed=0;}
 else {assert(!runtime.prepared&&!submits&&controller.stop_requested&&runtime.application_failure==(mode==2?XNOW_ENDPOINT_CRYPTO_UNAVAILABLE:XNOW_SECURITY_STORAGE));}
 close(in[1]);int r=XNOW_PENDING;for(unsigned i=0;r==XNOW_PENDING;i++){assert(i<200);r=xnow_owner_runtime_step(&runtime);}assert(!r&&runtime.done&&!clients&&connection==4&&data.file.directory==-1);
 uint8_t record[33];assert(read(handoff[0],record,sizeof record)==32&&!memcmp(record,"XRFDONE1",8));assert(read(handoff[0],record,sizeof record)==0);close(handoff[0]);close(out[0]);for(unsigned i=0;i<sizeof workspace;i++)assert(!((uint8_t *)&workspace)[i]);
}
int main(int argc,char **argv){assert(argc==3&&signal(SIGPIPE,SIG_IGN)!=SIG_ERR);io.read=transport_read;int fd=open(argv[1],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);struct stat st;assert(fd>=0&&!fstat(fd,&st));struct xnow_pn_file file={fd,(uint64_t)st.st_dev,0,directory_guard};fresh(&file,local,remote);fresh(&file,remote,local);assert(!close(fd));run(argv[1],0,1);run(argv[1],0,1025);run(argv[2],1,0);run(argv[2],2,0);run(argv[1],3,0);puts("Secure runtime: persistent PN1/1025, encrypted1470 TX/RX, replay/MIC and malformed-plaintext discard, valid unknown plaintext, real IO failure stop, missing/inert prepare refusal and cleanup passed; RF mocked.");return 0;}
