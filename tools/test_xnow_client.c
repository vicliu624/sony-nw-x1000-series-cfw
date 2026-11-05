#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#define XNOW_OWNER_COMMAND_TEST_MAIN server_baseline_checks
#include "test_xnow_owner_commands.c"
#include "../runtime/platform/espnow/xnow_owner_stream.h"
#include "../runtime/platform/espnow/xnow_client.h"
#include "../runtime/apps/wireless-remote/status_sender.h"
#include "../runtime/apps/wireless-remote/receiver.h"
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
#define fcntl fixture_fcntl
static size_t read_limit=3,write_limit=5;
extern ssize_t __real_read(int,void *,size_t);
extern ssize_t __real_write(int,const void *,size_t);
ssize_t __wrap_read(int fd,void *p,size_t n){return __real_read(fd,p,n>read_limit?read_limit:n);}
ssize_t __wrap_write(int fd,const void *p,size_t n){return __real_write(fd,p,n>write_limit?write_limit:n);}
static void nonblock(int fd){assert(fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)|O_NONBLOCK)>=0);}
static unsigned player_reads;
static unsigned player_commands;
static unsigned library_reads;
static unsigned library_busy;
static int player_browse(void *context,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 (void)context;library_reads++;if(library_busy){library_busy--;return XW_PLAYER_BUSY;}memset(items,0,sizeof *items);strcpy(items->id.value,"browse-track");strcpy(items->title,"Real SDK browse fixture");items->flags=XW_MEDIA_TITLE_PRESENT;
 *page=(struct xw_media_page){77,q->offset,1,2,q->offset+1};return 0;
}
static int player_command(void *context,const struct xw_player_command *c){(void)context;assert(c->operation==XW_OP_NEXT);player_commands++;return XW_PLAYER_UNCERTAIN;}
static int player_snapshot(void *context,struct xw_player_snapshot *s){
 (void)context;player_reads++;memset(s,0,sizeof *s);s->valid=39;s->state=XW_PLAY_PLAYING;
 s->volume=9;s->volume_max=30;s->track.flags=7;strcpy(s->track.id.value,"fixture-track");
 strcpy(s->track.title,"SDK to radio status");return 0;
}
static int player_close(void *context){(void)context;return 0;}
static void pump(struct xnow_client *client,struct xnow_owner_stream *server){
 for(unsigned i=0;!client->event_ready;i++){
  assert(i<10000);assert(xnow_client_step(client)>=0);assert(xnow_owner_stream_step(server)>=0);
 }
}
int main(void){
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);reset();
 struct xnow_full full;assert(!xnow_full_open(&full,&io,&layout));assert(!xnow_endpoint_init(&endpoint,&full,6,17,0,random4));
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_init(&commands,0,ready,stop));
 int input[2],output[2];assert(!pipe(input)&&!pipe(output));
 for(unsigned i=0;i<2;i++){nonblock(input[i]);nonblock(output[i]);}
 struct xnow_owner_stream server;assert(!xnow_owner_stream_open(&server,&commands,input[0],output[1]));
 close(input[0]);close(output[1]);
 static struct xnow_client client;
 assert(!xnow_client_adopt(&client,output[0],input[1]));
 assert(fcntl(client.input,F_GETFD)&FD_CLOEXEC);assert(fcntl(client.output,F_GETFD)&FD_CLOEXEC);
 struct xnow_client_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,(uint8_t[]){2,1,2,3,4,5},6);peer.channel=6;peer.version=2;peer.encrypt=1;memset(peer.lmk,0x5a,16);
 uint32_t token=0;assert(!xnow_client_peer(&client,&peer,0,&token)&&token==1);
 assert(!memcmp(client.request+26,peer.lmk,16));pump(&client,&server);
 for(unsigned i=0;i<sizeof client.request;i++)assert(!client.request[i]);
 struct xnow_client_event event;assert(!xnow_client_take(&client,&event,0,0)&&event.kind==XNOW_CLIENT_ACK&&event.request==token&&!event.result);
 peer.encrypt=0;assert(!xnow_client_peer(&client,&peer,1,&token)&&token==2);
 for(unsigned i=26;i<42;i++)assert(!client.request[i]);pump(&client,&server);
 assert(!xnow_client_take(&client,&event,0,0)&&!event.result);memset(peer.lmk,0,16);
 uint8_t binary[1470],returned[1470];for(unsigned i=0;i<sizeof binary;i++)binary[i]=(uint8_t)(i*17u);
 assert(!xnow_client_send(&client,peer.address,binary,sizeof binary,&token)&&token==3);pump(&client,&server);
 assert(!xnow_client_take(&client,&event,0,0)&&event.kind==XNOW_CLIENT_ACK&&!event.result);
 uint32_t unchanged=0xdeadbeef;assert(xnow_client_send(&client,peer.address,binary,1,&unchanged)==XNOW_CLIENT_PENDING&&unchanged==0xdeadbeef);
 struct xnow_owner_completion completion;assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_PENDING);
 done(0);assert(!xnow_owner_commands_poll(&commands,&completion));
 assert(!xnow_owner_stream_completion(&server,&completion));pump(&client,&server);
 assert(!xnow_client_take(&client,&event,0,0)&&event.kind==XNOW_CLIENT_TX&&event.request==3&&!client.tx_request);
 assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_AGAIN);
 receive(binary,sizeof binary);struct xnow_full_received received;uint8_t payload[1470];assert(!xnow_owner_commands_receive(&commands,payload,sizeof payload,&received));
 assert(!xnow_owner_stream_receive(&server,payload,sizeof payload,&received));pump(&client,&server);
 memset(&event,0xa5,sizeof event);struct xnow_client_event old=event;memset(returned,0xa5,sizeof returned);
 assert(xnow_client_take(&client,&event,returned,sizeof returned-1)==XNOW_CLIENT_ARGUMENT&&!memcmp(&event,&old,sizeof old)&&client.event_ready);
 for(unsigned i=0;i<sizeof returned;i++)assert(returned[i]==0xa5);
 assert(!xnow_client_take(&client,&event,returned,sizeof returned)&&event.kind==XNOW_CLIENT_RX&&event.bytes==1470&&!memcmp(binary,returned,sizeof binary));
 /* Real SDK client -> application adapter -> actual radio owner stream.
  * Player provider and RF hardware remain explicit fixtures. */
 static struct xw_player player;struct xw_player_provider provider={0};
 provider.api=XW_PLAYER_API;provider.snapshot=player_snapshot;provider.close=player_close;
 assert(!xw_player_bind(&player,&provider));
 /* The independent control SDK ledger must not replay uncertain skips. */
 struct xw_player controlled;memset(&controlled,0,sizeof controlled);
 provider.command=player_command;provider.commands=1u<<XW_OP_NEXT;provider.browse=player_browse;
 assert(!xw_player_bind(&controlled,&provider));
 struct wr_control_ledger ledger={0};struct wr_control control={123,1,XW_OP_NEXT,0};struct wr_control_receipt receipt;
 assert(!wr_control_dispatch(&ledger,&controlled,123,&control,&receipt)&&receipt.result==XW_PLAYER_UNCERTAIN&&player_commands==1);
 assert(!wr_control_dispatch(&ledger,&controlled,123,&control,&receipt)&&player_commands==1);
 control.operation=XW_OP_PAUSE;assert(wr_control_dispatch(&ledger,&controlled,123,&control,&receipt)==-1&&player_commands==1);
 control.operation=XW_OP_NEXT;control.request=2;assert(!wr_control_dispatch(&ledger,&controlled,123,&control,&receipt)&&player_commands==2);
 control.request=1;assert(wr_control_dispatch(&ledger,&controlled,123,&control,&receipt)==-1&&player_commands==2);
 assert(!xw_player_close(&controlled));
 static struct wr_sender sender;uint8_t auth[32]={7};
 assert(!wr_sender_init(&sender,&player,&client,peer.address,auth,123));
 assert(!wr_sender_sample(&sender)&&sender.sequence==1&&player_reads==1);
 struct wr_status actual;assert(!wr_status_verify(&actual,sender.wire,sizeof sender.wire,auth));
 assert(actual.state==XW_PLAY_PLAYING&&actual.volume==9&&!strcmp(actual.title,"SDK to radio status"));
 assert(wr_sender_sample(&sender)==XNOW_CLIENT_PENDING&&player_reads==1&&sender.sequence==1);
 for(unsigned i=0;!sender.submitted;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(sender.pending&&xnow_owner_commands_poll(&commands,&completion)==XNOW_PENDING);
 done(0);assert(!xnow_owner_commands_poll(&commands,&completion));assert(!xnow_owner_stream_completion(&server,&completion));
 for(unsigned i=0;sender.pending;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 struct wr_receiver receiver={0};uint8_t source[6]={2,9,8,7,6,5};assert(!wr_receiver_pair(&receiver,source,auth,123));
 assert(!wr_receiver_accept(&receiver,source,sender.wire,sizeof sender.wire)&&receiver.status.volume==9);
 assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_AGAIN);
 wr_receiver_clear(&receiver);
 assert(!xw_player_bind(&controlled,&provider));sender.player=&controlled;
 uint8_t control_wire[WR_CONTROL_BYTES];control=(struct wr_control){123,1,XW_OP_NEXT,0};
 assert(!wr_control_encode(control_wire,sizeof control_wire,&control,auth));
 memset(&received,0,sizeof received);memcpy(received.source,peer.address,6);
 received.info.version=2;received.info.elements=1;received.info.payload_bytes=sizeof control_wire;received.flags=XNOW_CLIENT_AUTHENTICATED;
 assert(!xnow_owner_stream_receive(&server,control_wire,sizeof control_wire,&received));
 for(unsigned i=0;!sender.receipt_ready;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(player_commands==3&&sender.ledger.result==XW_PLAYER_UNCERTAIN);
 assert(!wr_receipt_decode(&receipt,sender.receipt,sizeof sender.receipt,auth)&&receipt.result==XW_PLAYER_UNCERTAIN);
 for(unsigned i=0;!sender.submitted;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_PENDING);done(0);
 assert(!xnow_owner_commands_poll(&commands,&completion));assert(!xnow_owner_stream_completion(&server,&completion));
 for(unsigned i=0;sender.pending;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_AGAIN);
 uint8_t challenge[16]={3},session_wire[WR_SESSION_BYTES];uint64_t session=0;
 assert(!wr_receiver_pair(&receiver,source,auth,122));receiver.sequence=99;receiver.have_status=1;
 assert(!wr_receiver_challenge(&receiver,challenge,session_wire,sizeof session_wire));
 received.info.payload_bytes=sizeof session_wire;
 assert(!xnow_owner_stream_receive(&server,session_wire,sizeof session_wire,&received));
 for(unsigned i=0;!sender.session_ready;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(player_commands==3&&!wr_session_reply_read(&session,sender.session_reply,sizeof sender.session_reply,challenge,auth)&&session==123);
 assert(wr_receiver_session_reply(&receiver,source,sender.session_reply,sizeof sender.session_reply)==1&&receiver.session==123&&!receiver.have_status&&!receiver.sequence);
 for(unsigned i=0;!sender.submitted;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_PENDING);
 done(0);assert(!xnow_owner_commands_poll(&commands,&completion));assert(!xnow_owner_stream_completion(&server,&completion));
 for(unsigned i=0;sender.pending;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(!xnow_owner_stream_receive(&server,session_wire,sizeof session_wire,&received));
 for(unsigned i=0;i<200;i++){assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(!sender.session_ready&&!sender.pending&&player_commands==3);
 assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_AGAIN);
 struct wr_library_request query={0};query.session=123;query.request=1;query.query.limit=1;
 uint8_t library_request[WR_LIBRARY_REQUEST_BYTES];assert(!wr_library_request_encode(library_request,sizeof library_request,&query,auth));
 received.info.payload_bytes=sizeof library_request;
 library_busy=1;
 for(unsigned round=0;round<2;round++){
  assert(!xnow_owner_stream_receive(&server,library_request,sizeof library_request,&received));
  for(unsigned i=0;!sender.library_ready;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(wr_sender_library_tick(&sender,(uint64_t)i*100)>=0);assert(xnow_owner_stream_step(&server)>=0);}
  struct wr_library_reply reply;assert(!wr_library_reply_decode(&reply,sender.library_reply,sizeof sender.library_reply,auth));
  assert(!reply.result&&reply.page.count==1&&!strcmp(reply.item.id.value,"browse-track")&&library_reads==2);
  for(unsigned i=0;!sender.submitted;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
  assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_PENDING);done(0);
  assert(!xnow_owner_commands_poll(&commands,&completion));assert(!xnow_owner_stream_completion(&server,&completion));
  for(unsigned i=0;sender.pending;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
  assert(xnow_owner_commands_poll(&commands,&completion)==XNOW_AGAIN);
 }
 puts("REMOTE_LIBRARY_REAL_STREAM_DUPLICATE_PASS");
 query.request=2;query.query.offset=1;assert(!wr_library_request_encode(library_request,sizeof library_request,&query,auth));library_busy=100;
 assert(!xnow_owner_stream_receive(&server,library_request,sizeof library_request,&received));
 for(unsigned i=0;!sender.library_active;i++){assert(i<10000);assert(wr_sender_step(&sender)>=0);assert(xnow_owner_stream_step(&server)>=0);}
 assert(library_reads==3);assert(wr_sender_library_tick(&sender,10000)>=0);
 assert(wr_sender_library_tick(&sender,10099)>=0&&library_reads==3);
 assert(wr_sender_library_tick(&sender,10100)>=0&&library_reads==4);
 assert(wr_sender_library_tick(&sender,12000)>=0&&sender.library_ready&&!sender.library_active&&library_reads==4);
 struct wr_library_reply timeout;assert(!wr_library_reply_decode(&timeout,sender.library_reply,sizeof sender.library_reply,auth)&&timeout.result==XW_PLAYER_UNAVAILABLE);
 assert(!wr_library_dispatch(&sender.library_ledger,sender.player,123,&query,&timeout)&&timeout.result==XW_PLAYER_UNAVAILABLE&&library_reads==4);
 assert(!wr_sender_library_tick(&sender,13000)&&library_reads==4);
 puts("REMOTE_LIBRARY_ASYNC_CADENCE_AND_TIMEOUT_PASS");
 wr_receiver_clear(&receiver);wr_sender_clear(&sender);assert(!xw_player_close(&controlled));assert(!xw_player_close(&player));
 assert(!xnow_client_delete(&client,peer.address,&token)&&token==9);
 while(client.request_bytes)assert(xnow_client_step(&client)>=0);
 uint8_t bad[16]={0};memcpy(bad,"XNA1",4);le(bad+4,999);le(bad+12,3);
 for(unsigned i=0;i<sizeof bad;){ssize_t n=write(server.output,bad+i,sizeof bad-i);assert(n>0);i+=(unsigned)n;}
 int rc=0;for(unsigned i=0;i<100&&!client.fault;i++)rc=xnow_client_step(&client);
 assert(rc==XNOW_CLIENT_UNCERTAIN&&client.fault);
 assert(xnow_owner_stream_step(&server)==XNOW_IO&&stops==1);
 unsigned count,encrypted;xnow_peer_count(&endpoint.peers,&count,&encrypted);assert(count==1); /* Delete never replayed/dispatched after HUP. */
 assert(!xnow_owner_stream_close(&server));
 puts("XNOW_CLIENT_PASS: real partial FIFO client/server, key wiping,1470 TX/RX, retained capacity retry, mismatched ACK and no replay; radio synthetic.");return 0;
}
