#include "../../runtime/platform/player/managed_host.h"
#include "../../runtime/platform/services/descriptor.h"
#include <sys/socket.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
static unsigned commands,reads,browses,broker_closes;
static int mode_read(void *context,uint32_t *raw,uint32_t *index){(void)context;*raw=5;*index=4;return 0;}
static int snapshot(void *c,struct xw_player_snapshot *s){(void)c;reads++;s->valid=XW_PF_STATE;s->state=XW_PLAY_PLAYING;return 0;}
static int command(void *c,const struct xw_player_command *r){(void)c;(void)r;commands++;return 1;}
static int browse(void *c,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *p){(void)c;(void)items;browses++;p->offset=q->offset;p->count=p->total=p->next_offset=0;p->revision=0;return 0;}
static int original_close(void *c){(void)c;assert(0);return 0;}
static int broker_close(void *c){struct xw_player_broker *b=c;broker_closes++;b->backend=0;return 0;}
static void send_request(int fd,unsigned kind,unsigned serial){
 struct xw_rpc_request request={0};request.kind=kind;request.serial=serial;
 if(kind==XW_RPC_COMMAND)request.body.command.operation=XW_OP_NEXT;
 unsigned char frame[XW_RPC_REQUEST_MAX];size_t size;
 assert(!xw_rpc_encode_request(&request,frame,sizeof frame,&size));assert(write(fd,frame,size)==(ssize_t)size);
}
int main(void){
 static struct xw_player original;static struct xw_player_broker broker;
 static struct xw_player_session_offer a,b;static struct xw_managed_host host;
 struct xw_player_provider op={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,browse,original_close};
 assert(!xw_player_bind(&original,&op));
 struct xw_player_provider bp={XW_PLAYER_API,1u<<XW_OP_NEXT,&broker,snapshot,command,browse,broker_close};
 broker.backend=&original;assert(!xw_player_bind(&broker.player,&bp));
 struct xw_player_session_offer *offers[]={&a,&b};
 assert(!xw_managed_host_init(&host,&broker,31,7,offers,2));
 int delivery[2],first,second;struct xw_descriptor_offer identity,other;
 assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 assert(xw_managed_host_offer(&host,delivery[0],7,1,0)==XW_SESSION_DENIED);
 assert(!xw_managed_host_offer(&host,delivery[0],3,3,0));
 assert(!xw_service_descriptor_receive(delivery[1],&first,&identity));
 assert(!xw_managed_host_offer(&host,delivery[0],5,5,0));
 assert(!xw_service_descriptor_receive(delivery[1],&second,&other));
 assert(identity.session!=other.session&&xw_managed_host_offer(&host,delivery[0],1,1,0)==XW_PLAYER_BUSY);
 assert(!xw_managed_host_tick(&host,1)&&!reads); /* No sampling before adoption. */
 send_request(first,XW_RPC_HELLO,1);send_request(second,XW_RPC_HELLO,1);
 assert(!xw_managed_host_tick(&host,2)&&a.channel.hello&&b.channel.hello);
 assert(!xw_managed_host_tick(&host,3)&&reads==2&&a.player.events.last&&b.player.events.last);
 uint32_t mode_raw=99,mode_index=99;
 assert(xw_managed_player_mode_get(&a.player,&mode_raw,&mode_index)==XW_PLAYER_UNSUPPORTED&&mode_raw==99&&mode_index==99);
 assert(!xw_managed_player_mode_bind(&a.player,0,mode_read));
 assert(!xw_managed_player_mode_get(&a.player,&mode_raw,&mode_index)&&mode_raw==5&&mode_index==4);
 static struct xw_session_manager denied_manager;static struct xw_managed_player denied_player;struct xw_session_handle denied_handle;
 assert(!xw_sessions_init(&denied_manager,99,3)&&!xw_session_open(&denied_manager,2,2,&denied_handle));
 assert(!xw_managed_player_bind(&denied_player,&denied_manager,denied_handle,&broker.player));
 assert(!xw_managed_player_mode_bind(&denied_player,0,mode_read));mode_raw=mode_index=99;
 assert(xw_managed_player_mode_get(&denied_player,&mode_raw,&mode_index)==XW_PLAYER_UNAVAILABLE&&mode_raw==99&&mode_index==99);
 assert(!xw_managed_player_close(&denied_player));
 /* Native owner-loop frequency must not multiply background snapshots.
  * Channel commands below still dispatch before the next refresh interval. */
 for(unsigned tick=0;tick<1000;tick++)assert(!xw_managed_host_tick(&host,3));
 assert(reads==2);
 send_request(first,XW_RPC_COMMAND,2);send_request(second,XW_RPC_COMMAND,2);
 assert(!xw_managed_host_tick(&host,4)&&commands==1); /* B cannot control. */
 unsigned sampled=reads;
 assert(!xw_managed_host_tick(&host,202)&&reads==sampled);
 assert(!xw_managed_host_tick(&host,203)&&reads==sampled+2); /* Exact 200 ms boundary. */
 struct xw_media_query query={0};query.limit=1;static struct xw_media_item item;struct xw_media_page page;
 assert(xw_managed_player_browse(&a.player,&query,&item,1,&page)==XW_PLAYER_UNAVAILABLE);
 assert(!xw_managed_player_browse(&b.player,&query,&item,1,&page)&&browses==1);
 close(first);assert(!xw_managed_host_tick(&host,204)&&host.slots[0]==2&&host.slots[1]==1&&b.channel.bound);
 assert(!xw_managed_host_offer(&host,delivery[0],1,1,205));
 int replacement;struct xw_descriptor_offer newer;
 assert(!xw_service_descriptor_receive(delivery[1],&replacement,&newer)&&newer.session>other.session&&newer.session!=identity.session);
 assert(!xw_managed_host_tick(&host,3205)&&host.slots[0]==2&&b.channel.bound); /* Silent claimant only. */
 close(replacement);
 for(unsigned i=0;i<8;i++){
  uint64_t now=4000u+i*4000u;
  assert(!xw_managed_host_offer(&host,delivery[0],1,1,now));
  struct xw_descriptor_offer recycled;int abandoned;
  assert(!xw_service_descriptor_receive(delivery[1],&abandoned,&recycled)&&recycled.session>newer.session);
  newer=recycled;
  assert(!xw_managed_host_tick(&host,now+3000)&&host.slots[0]==2&&host.slots[1]==1&&b.channel.bound);
  close(abandoned);
 }
 assert(xw_managed_host_stop(&host,XW_SESSION_USB)==XW_PLAYER_BUSY&&!host.manager.accepting);
 assert(xw_managed_host_offer(&host,delivery[0],1,1,3007)==XW_PLAYER_CLOSED);
 assert(!xw_managed_host_tick(&host,3007)&&host.phase==XW_HOST_STOPPED&&broker_closes==1&&original.initialized);
 assert(!xw_managed_host_tick(&host,3008)&&!xw_managed_host_stop(&host,XW_SESSION_USB)&&broker_closes==1);
 close(second);close(delivery[0]);close(delivery[1]);
 puts("Managed host: grants, adoption, notifications, browse, isolated close, reuse and complete drain passed");return 0;
}
