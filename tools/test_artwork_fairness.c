/* Actual sender/worker with RX arriving before the prior TX completion. */
#define main existing_sender_checks
#include "test_status_sender.c"
#undef main
#include "../runtime/apps/wireless-remote/worker.h"
#include "../runtime/apps/wireless-remote/on_demand_link.h"
#include "../runtime/apps/wireless-remote/transport_goal.h"
int xnow_client_close(struct xnow_client *c){c->used=0;return 0;}
static int retired(void *unused){(void)unused;return 0;}
static void art_request(struct wr_sender *s,unsigned serial,unsigned offset){
 struct wr_artwork_request r={0};r.session=s->session;r.request=serial;r.offset=offset;strcpy(r.id.value,"song-art");
 assert(!wr_artwork_request_encode(incoming,sizeof incoming,&r,s->key));
 queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;queued.bytes=WR_ARTWORK_REQUEST_BYTES;memcpy(queued.address,s->peer,6);
 assert(wr_sender_step(s)==XNOW_CLIENT_PENDING&&s->artwork_active);
}
static void cover_survives_unconfirmed_control(void){
 struct xw_player player={0};
 struct xw_player_provider provider={XW_PLAYER_API,3,0,snapshot,control,0,close_player};
 struct xnow_client radio={0};radio.used=1;
 uint8_t peer[6]={2,1,2,3,4,5},key[32]={1};
 struct wr_sender sender={0};static struct wr_artwork_client client;
 memset(&client,0,sizeof client);
 struct wr_status status={0};struct wr_transport_goal goal={0};
 assert(!xw_player_bind(&player,&provider)&&!wr_sender_init(&sender,&player,&radio,peer,key,73));
 sender.artwork_read=read_cover;
 status.session=73;status.sequence=1;status.valid=XW_PF_STATE|XW_PF_TRACK;
 status.state=XW_PLAY_PLAYING;strcpy(status.id,"song-art");
 for(unsigned i=0;i<sizeof picture;i++)picture[i]=(unsigned char)(i*7u);
 wr_transport_goal_begin(&goal,&status,1,XW_OP_PAUSE,100);
 struct wr_control_receipt receipt={73,1,XW_PLAYER_ACCEPTED};
 wr_transport_goal_receipt(&goal,&receipt);
 unsigned expired=0,chunks=0;
 for(uint64_t now=100;!client.job.complete;now+=150){
  assert(now<30000);
  if(wr_transport_goal_expire(&goal,now)){
   expired++;
   /* This is the decision used by the real frontend: command completion is
    * still unknown, but its authenticated response must not drop the link. */
   assert(!wr_transport_goal_needs_link_check(&goal));
  }
  wr_artwork_client_observe(&client,&status,1,now);
  if(goal.request)continue;
  if(!client.job.pending){
   assert(!wr_artwork_client_request(&client,now,incoming,sizeof incoming,key));
   queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;
   queued.bytes=WR_ARTWORK_REQUEST_BYTES;memcpy(queued.address,peer,6);
   assert(wr_sender_step(&sender)==XNOW_CLIENT_PENDING);
  }
  assert(!wr_sender_artwork_tick(&sender));
  assert(wr_sender_step(&sender)==XNOW_CLIENT_AGAIN&&sender.pending);
  assert(!wr_artwork_client_accept(&client,now,wire,wire_bytes,key));finish(&sender);chunks++;
 }
 assert(expired==1&&chunks==(sizeof picture+WR_ARTWORK_DATA_BYTES-1)/WR_ARTWORK_DATA_BYTES);
 assert(client.job.received==sizeof picture&&!memcmp(client.data,picture,sizeof picture));
 assert(!xw_player_close(&player));wr_sender_clear(&sender);
 puts("CONTROL_ARTWORK_PROGRESS_PASS: a slow authenticated cover completes after an accepted but unconfirmed playback goal expires");
}
int main(void){
 struct wr_demand_link link={0};
 for(uint64_t now=0;now<3600000;now+=1000)assert(!wr_demand_step(&link,now));
 wr_demand_request(&link);assert(wr_demand_step(&link,3600000)==1);
 wr_demand_request(&link);assert(!wr_demand_step(&link,3601000));
 assert(wr_demand_step(&link,3603000)==-1);
 for(uint64_t now=3603001;now<7200000;now+=1000)assert(!wr_demand_step(&link,now));
 wr_demand_request(&link);assert(wr_demand_step(&link,7200000)==1);wr_demand_complete(&link);
 assert(!wr_demand_step(&link,999999999));
 struct xw_player p={0};struct xw_player_provider provider={XW_PLAYER_API,3,0,snapshot,control,0,close_player};
 assert(!xw_player_bind(&p,&provider));struct xnow_client radio={0};radio.used=1;
 uint8_t peer[6]={2,1,2,3,4,5},key[32]={1};struct wr_sender s={0};struct wr_worker w={0};
 assert(!wr_sender_init(&s,&p,&radio,peer,key,17));s.artwork_read=read_cover;
 assert(!wr_worker_init(&w,&s,0,close_player,retired));
 assert(wr_worker_step(&w,100)==XW_PLAYER_BUSY&&s.pending);finish(&s);
 art_request(&s,1,0);assert(!wr_sender_artwork_tick(&s)&&s.artwork_ready);
 unsigned updates=0;
 for(unsigned i=1;i<=40;i++){
  if(s.pending)finish(&s);
  if(s.artwork_active)assert(!wr_sender_artwork_tick(&s));
  assert(s.artwork_ready);assert(wr_sender_step(&s)==XNOW_CLIENT_AGAIN&&s.pending);
  assert(!memcmp(wire,"WRAR",4));
  queued.kind=XNOW_CLIENT_ACK;queued.request=s.request;queued.operation=4;
  assert(wr_sender_step(&s)==XNOW_CLIENT_PENDING);
  if(i%WR_ARTWORK_WINDOW_CHUNKS==0)art_request(&s,i+1,i*WR_ARTWORK_DATA_BYTES);
  if(i==15)volume=11;
  queued.kind=XNOW_CLIENT_TX;queued.request=s.request;memcpy(queued.address,s.peer,6);
  assert(wr_worker_step(&w,(uint64_t)i*1000)==XW_PLAYER_BUSY);
  if(i==15){assert(s.pending&&wr_status_frame(wire,wire_bytes)&&s.status.volume==11);updates++;}
 }
 assert(updates==1);
 puts("ARTWORK_FAIRNESS_PASS: a changed state preempts continuous cover requests before the next chunk; no idle reconnect probes");
 cover_survives_unconfirmed_control();return 0;
}
