/* Real sender/receiver codecs and player client; modeled radio completion. */
#include "../runtime/apps/wireless-remote/status_sender.h"
#include "../runtime/apps/wireless-remote/receiver.h"
#include "../runtime/apps/wireless-remote/artwork_client.h"
#include "../runtime/apps/wireless-remote/artwork_image.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static unsigned transmissions;static size_t wire_bytes;static uint8_t wire[1470];
static struct xnow_client_event queued;static uint8_t incoming[1470];
static int volume=10,snapshot_result,source_live=1;
static unsigned playback_state=XW_PLAY_PLAYING,control_calls;
static int control_result=XW_PLAYER_ACCEPTED;
static int alive(void *p){(void)p;return source_live;}
static unsigned cover_reads;
static unsigned char picture[85474];
static int read_cover(void *p,uint32_t offset,struct xw_artwork_chunk *out){
 (void)p;cover_reads++;if(offset>=sizeof picture)return XW_PLAYER_INVALID;memset(out,0,sizeof *out);strcpy(out->id.value,"song-art");out->total=sizeof picture;out->offset=offset;
 out->bytes=out->total-offset;if(out->bytes>XW_ARTWORK_CHUNK)out->bytes=XW_ARTWORK_CHUNK;memcpy(out->data,picture+offset,out->bytes);return 0;
}
static int snapshot(void *p,struct xw_player_snapshot *s){
 (void)p;if(snapshot_result)return snapshot_result;memset(s,0,sizeof *s);s->valid=XW_PF_STATE|XW_PF_VOLUME;s->state=playback_state;
 s->volume=volume;s->volume_max=30;return 0;
}
static int control(void *p,const struct xw_player_command *c){(void)p;(void)c;control_calls++;return control_result;}
static int close_player(void *p){(void)p;return 0;}
int xnow_client_send(struct xnow_client *c,const uint8_t peer[6],const void *p,size_t bytes,uint32_t *request){
 (void)c;(void)peer;assert(bytes<=sizeof wire);memcpy(wire,p,bytes);wire_bytes=bytes;*request=++transmissions;return 0;
}
int xnow_client_step(struct xnow_client *c){(void)c;return 0;}
int xnow_client_take(struct xnow_client *c,struct xnow_client_event *e,void *p,size_t capacity){
 (void)c;if(!queued.kind)return XNOW_CLIENT_AGAIN;assert(queued.bytes<=capacity);memcpy(p,incoming,queued.bytes);*e=queued;memset(&queued,0,sizeof queued);return 0;
}
static void finish(struct wr_sender *s){
 queued.kind=XNOW_CLIENT_ACK;queued.request=s->request;queued.operation=4;
 assert(wr_sender_step(s)==XNOW_CLIENT_PENDING);
 queued.kind=XNOW_CLIENT_TX;queued.request=s->request;memcpy(queued.address,s->peer,6);
 assert(!wr_sender_step(s)&&!s->pending);
}
static void transient_track_observation(void){
 static struct wr_artwork_client client;memset(&client,0,sizeof client);
 struct wr_status status={0},unknown={0};
 status.session=17;status.valid=XW_PF_TRACK;strcpy(status.id,"song-art");unknown.session=17;
 uint8_t key[32]={1},request[WR_ARTWORK_REQUEST_BYTES],reply[WR_ARTWORK_REPLY_MAX];
 wr_artwork_client_observe(&client,&status,1,100);
 assert(!wr_artwork_client_request(&client,100,request,sizeof request,key));
 struct wr_artwork_request asked;assert(!wr_artwork_request_decode(&asked,request,sizeof request,key));
 struct wr_artwork_reply image={0};image.session=17;image.request=asked.request;
 image.chunk.id=asked.id;image.chunk.total=2048;image.chunk.bytes=1024;
 memset(image.chunk.data,0xa5,1024);
 int bytes=wr_artwork_reply_encode(reply,sizeof reply,&image,key);assert(bytes>0);
 assert(!wr_artwork_client_accept(&client,100,reply,bytes,key)&&client.job.received==1024);
 assert(!wr_artwork_client_request(&client,300,request,sizeof request,key));
 assert(!wr_artwork_request_decode(&asked,request,sizeof request,key));
 image.request=asked.request;image.chunk.offset=1024;memset(image.chunk.data,0x5a,1024);
 bytes=wr_artwork_reply_encode(reply,sizeof reply,&image,key);assert(bytes>0);
 /* A live authenticated status can temporarily lack track identity while
  * AudioC is busy. It is not a session revocation or a different track. */
 wr_artwork_client_observe(&client,&unknown,1,350);
 assert(client.job.session==17&&client.job.received==1024&&!strcmp(client.job.id.value,"song-art"));
 assert(!wr_artwork_client_image_ready(&client));
 assert(wr_artwork_client_request(&client,500,request,sizeof request,key));
 assert(wr_artwork_client_accept(&client,500,reply,bytes,key)&&client.job.received==1024);
 wr_artwork_client_observe(&client,&status,1,1000);
 assert(!wr_artwork_client_request(&client,1000,request,sizeof request,key));
 assert(!wr_artwork_request_decode(&asked,request,sizeof request,key)&&asked.offset==1024&&asked.request==image.request);
 assert(!wr_artwork_client_accept(&client,1000,reply,bytes,key)&&wr_artwork_client_image_ready(&client));
 assert(client.data[0]==0xa5&&client.data[1024]==0x5a);
 wr_artwork_client_observe(&client,&unknown,1,1100);assert(client.job.complete&&client.job.received==2048&&!wr_artwork_client_image_ready(&client));
 wr_artwork_client_observe(&client,&status,1,1200);assert(wr_artwork_client_image_ready(&client)&&client.job.received==2048);
 strcpy(status.id,"another-track");wr_artwork_client_observe(&client,&status,1,1300);
 assert(!client.job.complete&&!client.job.received);
 unknown.session=18;wr_artwork_client_observe(&client,&unknown,1,1400);
 assert(!client.job.session&&wr_artwork_client_accept(&client,1400,reply,bytes,key));
 puts("TRANSIENT_TRACK_OBSERVATION_PASS: unknown track pauses assembly, confirmed same identity resumes, new identity/session revokes");
}
static void artwork_retry_boundaries(void){
 static struct wr_artwork_client client;memset(&client,0,sizeof client);
 struct wr_status status={0},unknown={0};status.session=unknown.session=29;
 status.valid=XW_PF_TRACK;strcpy(status.id,"epoch-art");
 uint8_t key[32]={1},request[WR_ARTWORK_REQUEST_BYTES],wire[WR_ARTWORK_REPLY_MAX];
 wr_artwork_client_observe(&client,&status,1,100);
 assert(!wr_artwork_client_request(&client,100,request,sizeof request,key));
 struct wr_artwork_reply chunk={0};chunk.session=29;chunk.request=client.job.serial;
 chunk.chunk.id=client.job.id;chunk.chunk.total=2048;chunk.chunk.bytes=1024;
 memset(chunk.chunk.data,0xa5,1024);
 int count=wr_artwork_reply_encode(wire,sizeof wire,&chunk,key);assert(count>0);
 assert(!wr_artwork_client_accept(&client,100,wire,count,key)&&client.job.received==1024);
 assert(!wr_artwork_client_request(&client,300,request,sizeof request,key));
 uint32_t first=client.job.serial;uint64_t deadline=client.job.deadline;
 struct wr_artwork_reply changed={0};changed.session=29;changed.request=first;
 changed.result=XW_PLAYER_STALE;changed.chunk.id=client.job.id;changed.chunk.offset=1024;
 int bytes=wr_artwork_reply_encode(wire,sizeof wire,&changed,key);assert(bytes>0);
 assert(!wr_artwork_client_accept(&client,300,wire,bytes,key));
 assert(client.job.restarts==1&&!client.job.received&&!client.job.pending&&client.job.deadline==deadline);
 assert(!wr_artwork_client_request(&client,450,request,sizeof request,key));
 chunk.request=client.job.serial;memset(chunk.chunk.data,0xb6,1024);
 count=wr_artwork_reply_encode(wire,sizeof wire,&chunk,key);assert(count>0);
 assert(!wr_artwork_client_accept(&client,450,wire,count,key));
 assert(!wr_artwork_client_request(&client,650,request,sizeof request,key));
 chunk.request=client.job.serial;chunk.chunk.offset=1024;memset(chunk.chunk.data,0xc7,1024);
 count=wr_artwork_reply_encode(wire,sizeof wire,&chunk,key);assert(count>0);
 assert(!wr_artwork_client_accept(&client,650,wire,count,key)&&wr_artwork_client_image_ready(&client));
 assert(client.data[0]==0xb6&&client.data[1024]==0xc7);
 assert(!wr_artwork_client_retry(&client,1000));
 deadline=client.job.deadline;
 assert(!wr_artwork_client_request(&client,1000,request,sizeof request,key));
 first=client.job.serial;changed.request=first;changed.chunk.offset=0;
 bytes=wr_artwork_reply_encode(wire,sizeof wire,&changed,key);assert(bytes>0);
 assert(!wr_artwork_client_accept(&client,1000,wire,bytes,key));
 for(unsigned restart=1;restart<=WR_ARTWORK_RESTART_LIMIT;restart++){
  uint64_t now=1000+restart*WR_ARTWORK_PACE_MS;
  assert(!wr_artwork_client_request(&client,now,request,sizeof request,key));
  assert(client.job.serial>first);first=client.job.serial;changed.request=first;
  bytes=wr_artwork_reply_encode(wire,sizeof wire,&changed,key);assert(bytes>0);
  assert(!wr_artwork_client_accept(&client,now,wire,bytes,key));
 }
 assert(client.job.failed&&client.job.restarts==WR_ARTWORK_RESTART_LIMIT&&client.job.deadline==deadline);
 assert(!wr_artwork_client_retry(&client,2000)&&client.job.serial==first);
 for(unsigned attempt=0;attempt<WR_ARTWORK_ATTEMPT_LIMIT;attempt++){
  uint64_t now=2000+attempt*WR_ARTWORK_BUSY_MS;
  assert(!wr_artwork_client_request(&client,now,request,sizeof request,key));
  assert(client.job.serial==first+1);
  wr_artwork_client_send_rejected(&client,now);
 }
 assert(client.job.failed&&client.job.local_rejects==WR_ARTWORK_ATTEMPT_LIMIT);
 assert(!wr_artwork_client_retry(&client,4000));
 wr_artwork_client_observe(&client,&unknown,1,4100);
 assert(wr_artwork_client_retry(&client,4200));
 wr_artwork_client_tick(&client,client.job.deadline);assert(client.job.failed);
 wr_artwork_client_observe(&client,&status,1,client.job.deadline+1);assert(client.job.failed);
 assert(!wr_artwork_client_retry(&client,client.job.deadline+2));
 puts("ARTWORK_RETRY_BOUNDARIES_PASS: epoch restarts and local refusals are bounded, serials stay monotonic, paused jobs keep their deadline");
}
static void unchanged_control_resynchronizes(void){
 struct xw_player player={0};
 struct xw_player_provider provider={XW_PLAYER_API,3,0,snapshot,control,0,close_player};
 struct xnow_client radio={0};radio.used=1;
 struct wr_sender sender={0};struct wr_receiver receiver={0};
 uint8_t peer[6]={2,1,2,3,4,5},key[32]={1};
 snapshot_result=0;playback_state=XW_PLAY_PLAYING;control_result=XW_PLAYER_OK;control_calls=0;
 assert(!xw_player_bind(&player,&provider));
 assert(!wr_sender_init(&sender,&player,&radio,peer,key,42));
 assert(!wr_receiver_pair(&receiver,peer,key,42));
 sender.now=100;assert(!wr_sender_sample(&sender));
 assert(!wr_receiver_accept(&receiver,peer,wire,wire_bytes));finish(&sender);
 /* Native PAUSED state was sent once but not received. A MAC completion is
  * not an application receipt; the receiver still displays PLAYING. */
 playback_state=XW_PLAY_PAUSED;sender.now=1100;assert(!wr_sender_sample(&sender));
 queued.kind=XNOW_CLIENT_ACK;queued.request=sender.request;queued.operation=4;
 assert(wr_sender_step(&sender)==XNOW_CLIENT_PENDING);
 queued.kind=XNOW_CLIENT_TX;queued.request=sender.request;queued.stock_status=1;
 memcpy(queued.address,peer,6);assert(!wr_sender_step(&sender));
 assert(receiver.status.state==XW_PLAY_PLAYING&&sender.status.state==XW_PLAY_PAUSED);
 struct wr_control command={42,1,XW_OP_PAUSE,0};
 assert(!wr_control_encode(incoming,sizeof incoming,&command,key));
 queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;
 queued.bytes=WR_CONTROL_BYTES;memcpy(queued.address,peer,6);
 assert(wr_sender_step(&sender)==XNOW_CLIENT_PENDING&&control_calls==1);
 assert(wr_sender_step(&sender)==XNOW_CLIENT_AGAIN);finish(&sender);
 unsigned previous=transmissions;sender.now=1200;
 assert(!wr_sender_sample(&sender));
 assert(sender.pending&&transmissions==previous+1);
 assert(!wr_receiver_accept(&receiver,peer,wire,wire_bytes)&&receiver.status.state==XW_PLAY_PAUSED);
 finish(&sender);
 previous=transmissions;
 for(sender.now=2200;sender.now<3622000;sender.now+=1000)
  assert(!wr_sender_sample(&sender)&&transmissions==previous);
 assert(!xw_player_close(&player));wr_sender_clear(&sender);wr_receiver_clear(&receiver);
 playback_state=XW_PLAY_PLAYING;control_result=XW_PLAYER_ACCEPTED;
 puts("UNCHANGED_CONTROL_RESYNC_PASS: an explicit idempotent command refreshes lost status without heartbeat or control replay");
}
static void fresh_resume_while_snapshot_pending(void){
 struct xw_player player={0};
 struct xw_player_provider provider={XW_PLAYER_API,3,0,snapshot,control,0,close_player};
 assert(!xw_player_bind(&player,&provider));
 struct xnow_client radio={0};radio.used=1;
 uint8_t peer[6]={2,1,2,3,4,5},key[32]={1},challenge[16]={1};
 struct wr_sender sender={0};snapshot_result=0;source_live=1;
 assert(!wr_sender_init(&sender,&player,&radio,peer,key,17));
 sender.now=100;assert(!wr_sender_sample(&sender));finish(&sender);
 unsigned controls_before=control_calls;
 for(unsigned attempt=0;attempt<3;attempt++){
  /* Attempt1 is a new explicit nonce without a new status sample. Attempt2
   * repeats that nonce after a lost reply and must receive its cached result. */
  challenge[0]=attempt?2:1;
  assert(!wr_session_resume_request(incoming,WR_SESSION_BYTES,challenge,key));
  queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;
  queued.bytes=WR_SESSION_BYTES;memcpy(queued.address,peer,6);
  assert(wr_sender_step(&sender)==XNOW_CLIENT_PENDING&&sender.session_ready);
  assert(sender.sequence==1&&sender.resync_serial==(attempt?2u:1u));
  assert(wr_sender_step(&sender)==XNOW_CLIENT_AGAIN&&sender.pending);
  uint64_t session=0;struct wr_session_progress progress;
  assert(!wr_session_resume_reply_read(&session,&progress,wire,wire_bytes,challenge,key));
  assert(session==17&&progress.status==1&&!progress.control&&!progress.library);
  finish(&sender);
 }
 /* A forged request must not replace the cached authenticated reply. */
 uint8_t cached[WR_SESSION_BYTES];memcpy(cached,sender.session_reply,sizeof cached);
 assert(!wr_session_resume_request(incoming,WR_SESSION_BYTES,challenge,key));
 incoming[48]^=1;queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;
 queued.bytes=WR_SESSION_BYTES;memcpy(queued.address,peer,6);
 assert(wr_sender_step(&sender)==XNOW_CLIENT_AGAIN&&!sender.session_ready);
 assert(!memcmp(cached,sender.session_reply,sizeof cached)&&sender.resync_serial==2);
 assert(sender.force_status&&!wr_sender_sample(&sender)&&sender.sequence==2);
 finish(&sender);
 unsigned sent=transmissions;
 for(sender.now=1000;sender.now<10000;sender.now+=1000)
  assert(!wr_sender_sample(&sender)&&transmissions==sent);
 assert(control_calls==controls_before&&!xw_player_close(&player));wr_sender_clear(&sender);
 puts("FRESH_SESSION_RETRY_PASS: fresh nonce independent of media sequence, cached duplicate reply, forged refusal and no idle traffic");
}
int main(void){
 struct xw_player player={0};struct xw_player_provider provider={XW_PLAYER_API,3,0,snapshot,control,0,close_player};
 assert(!xw_player_bind(&player,&provider));struct xnow_client radio={0};radio.used=1;
 uint8_t peer[6]={2,1,2,3,4,5},key[32]={1};struct wr_sender s={0};struct wr_receiver r={0};
 assert(!wr_sender_init(&s,&player,&radio,peer,key,17)&&!wr_receiver_pair(&r,peer,key,17));
 s.now=100;assert(!wr_sender_sample(&s)&&transmissions==1&&wr_status_frame(wire,wire_bytes));
 assert(!wr_receiver_accept(&r,peer,wire,wire_bytes));finish(&s);
 for(s.now=1100;s.now<10100;s.now+=1000)assert(!wr_sender_sample(&s)&&transmissions==1);
 for(s.now=10100;s.now<3600100;s.now+=1000)assert(!wr_sender_sample(&s)&&transmissions==1&&!s.pending);
 volume=11;s.now=3600200;assert(!wr_sender_sample(&s)&&transmissions==2&&wr_status_frame(wire,wire_bytes));
 assert(!wr_receiver_accept(&r,peer,wire,wire_bytes)&&r.status.volume==11);finish(&s);
 uint8_t challenge[16]={1};assert(!wr_session_resume_request(incoming,WR_SESSION_BYTES,challenge,key));
 queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;queued.bytes=WR_SESSION_BYTES;memcpy(queued.address,peer,6);
 assert(wr_sender_step(&s)==XNOW_CLIENT_PENDING&&s.force_status&&s.resync_serial==1);
 assert(wr_sender_step(&s)==XNOW_CLIENT_AGAIN&&s.pending);finish(&s);
 assert(!wr_sender_sample(&s)&&transmissions==4&&wr_status_frame(wire,wire_bytes)&&!s.force_status);
 finish(&s);
 static struct wr_artwork_client c;struct wr_status art={0};art.session=17;art.sequence=4;art.valid=2;strcpy(art.id,"song-art");
 for(unsigned i=0;i<sizeof picture;i++)picture[i]=(unsigned char)i;
 wr_artwork_client_observe(&c,&art,1,100);s.artwork_read=read_cover;
 uint64_t now=100;
 while(!c.job.complete){
  assert(!wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
  queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;queued.bytes=WR_ARTWORK_REQUEST_BYTES;memcpy(queued.address,peer,6);
  assert(wr_sender_step(&s)==XNOW_CLIENT_PENDING&&s.artwork_active);
  if(!c.job.received){
   struct wr_control command={17,1,XW_OP_PLAY,0};assert(!wr_control_encode(incoming,sizeof incoming,&command,key));
   queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;queued.bytes=WR_CONTROL_BYTES;memcpy(queued.address,peer,6);
   assert(wr_sender_step(&s)==XNOW_CLIENT_PENDING&&s.receipt_ready);
   assert(!wr_sender_artwork_tick(&s)&&!cover_reads);
   assert(wr_sender_step(&s)==XNOW_CLIENT_AGAIN&&wire_bytes==WR_CONTROL_BYTES);finish(&s);
  }
  assert(!wr_sender_artwork_tick(&s)&&s.artwork_ready);
  assert(wr_sender_step(&s)==XNOW_CLIENT_AGAIN&&wire_bytes>=113&&wire_bytes<=WR_ARTWORK_REPLY_MAX);
  uint32_t received=c.job.received;wire[wire_bytes-1]^=1;assert(wr_artwork_client_accept(&c,now,wire,wire_bytes,key)&&c.job.received==received);wire[wire_bytes-1]^=1;
  assert(!wr_artwork_client_accept(&c,now,wire,wire_bytes,key));finish(&s);now+=200;
 }
 assert(c.job.total==sizeof picture&&cover_reads==(sizeof picture+XW_ARTWORK_CHUNK-1)/XW_ARTWORK_CHUNK&&!memcmp(c.data,picture,sizeof picture));
 struct wr_artwork_request eof={0};eof.session=17;eof.request=c.job.serial+1;eof.offset=sizeof picture;strcpy(eof.id.value,"song-art");
 assert(!wr_artwork_request_encode(incoming,sizeof incoming,&eof,key));
 queued.kind=XNOW_CLIENT_RX;queued.flags=XNOW_CLIENT_AUTHENTICATED;queued.bytes=WR_ARTWORK_REQUEST_BYTES;memcpy(queued.address,peer,6);
 assert(wr_sender_step(&s)==XNOW_CLIENT_PENDING&&!wr_sender_artwork_tick(&s));
 assert(wr_sender_step(&s)==XNOW_CLIENT_AGAIN&&s.active&&wire_bytes==113);
 struct wr_artwork_reply refused;assert(!wr_artwork_reply_decode(&refused,wire,wire_bytes,key)&&refused.result==XW_PLAYER_INVALID);finish(&s);
 assert(wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
 strcpy(art.id,"other-song");wr_artwork_client_observe(&c,&art,1,now);assert(!c.job.complete&&!c.job.received);
 assert(!wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
 assert(wr_artwork_client_accept(&c,now,wire,wire_bytes,key)&&!c.job.received);
 wr_artwork_client_tick(&c,now+2000);assert(!c.job.pending);
 struct wr_artwork_reply late_chunk={0};late_chunk.session=c.job.session;late_chunk.request=c.job.serial;late_chunk.chunk.id=c.job.id;
 late_chunk.chunk.total=128;late_chunk.chunk.bytes=128;
 int late_bytes=wr_artwork_reply_encode(wire,sizeof wire,&late_chunk,key);assert(late_bytes>0);
 assert(!wr_artwork_client_accept(&c,now+2050,wire,(size_t)late_bytes,key)&&c.job.complete&&c.job.received==128);
 art.session++;wr_artwork_client_observe(&c,&art,1,now+2100);
 assert(!wr_artwork_client_request(&c,now+2100,incoming,sizeof incoming,key));uint32_t original_request=c.job.serial;
 wr_artwork_client_tick(&c,now+4100);assert(!c.job.pending);
 assert(!wr_artwork_client_request(&c,now+4200,incoming,sizeof incoming,key)&&c.job.serial==original_request);
 wr_artwork_client_observe(&c,&art,0,now+4300);assert(!c.job.session&&!c.job.complete&&!c.job.pending);
 /* Initial metadata readiness and cover readiness are separate. A finite
  * retry handles late covers; permanent absence never becomes idle polling. */
 now+=5000;wr_artwork_client_observe(&c,&art,1,now);
 for(unsigned busy=0;busy<5;busy++){
  assert(!wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
  struct wr_artwork_reply waiting={0};waiting.session=art.session;waiting.request=c.job.pending;waiting.chunk.id=c.job.id;waiting.result=XW_PLAYER_BUSY;
  int n=wr_artwork_reply_encode(wire,sizeof wire,&waiting,key);assert(n>0);
  assert(!wr_artwork_client_accept(&c,now,wire,(size_t)n,key)&&!c.job.attempts&&!c.job.failed);now+=300;
 }
 assert(!wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
 wr_artwork_client_tick(&c,now+2000);assert(!c.job.pending&&!c.job.failed&&c.job.timeouts==1);
 now+=3000;art.session++;wr_artwork_client_observe(&c,&art,1,now);
 for(unsigned attempt=0;attempt<5;attempt++){
  assert(!wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
  struct wr_artwork_reply late={0};late.session=art.session;late.request=c.job.pending;late.chunk.id=c.job.id;late.result=XW_PLAYER_UNAVAILABLE;
  int n=wr_artwork_reply_encode(wire,sizeof wire,&late,key);assert(n>0);
  assert(!wr_artwork_client_accept(&c,now,wire,(size_t)n,key));
  assert(c.job.failed==(attempt==4)&&c.job.last_result==XW_PLAYER_UNAVAILABLE&&c.job.replies==attempt+1);
  now+=1000;
 }
 assert(wr_artwork_client_request(&c,now,incoming,sizeof incoming,key));
 unsigned width=0,height=0;const uint8_t jpeg[]={255,216,255,192,0,11,8,3,32,3,32,1,1,0,0};
 assert(wr_artwork_dimensions(jpeg,sizeof jpeg,&width,&height)==1&&width==800&&height==800);
 for(unsigned n=0;n<13;n++)assert(!wr_artwork_dimensions(jpeg,n,&width,&height));
 puts("ARTWORK_CHAIN_PASS: authenticated chunks, playback receipt priority, current-track assembly, no idle refetch, stale/corrupt rejection and bounded image dimensions");
 s.source_alive=alive;snapshot_result=XW_PLAYER_BUSY;s.now+=2000;
 assert(!wr_sender_sample(&s)&&s.pending);struct wr_status unavailable;
 assert(!wr_status_verify(&unavailable,wire,wire_bytes,key)&&!unavailable.valid&&!unavailable.id[0]&&!unavailable.title[0]);finish(&s);
 snapshot_result=XW_PLAYER_UNAVAILABLE;s.now+=1000;unsigned sent=transmissions;
 assert(!wr_sender_sample(&s)&&!s.pending&&transmissions==sent);
 source_live=0;assert(wr_sender_sample(&s)==XW_PLAYER_UNAVAILABLE&&transmissions==sent);
 source_live=1;snapshot_result=0;assert(!wr_sender_sample(&s)&&s.pending);finish(&s);
 puts("STATUS_SENDER_PASS: unchanged states suppressed, one-hour idle silence, reconnect snapshot, live-channel transient observations and closed-channel refusal");
 unchanged_control_resynchronizes();transient_track_observation();artwork_retry_boundaries();fresh_resume_while_snapshot_pending();return 0;
}
