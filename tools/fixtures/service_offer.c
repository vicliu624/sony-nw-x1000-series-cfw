#include "../../runtime/platform/player/session_offer.h"
#include "../../runtime/platform/services/descriptor.h"
#include <sys/socket.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
static unsigned commands;
static int snapshot(void *c,struct xw_player_snapshot *s){(void)c;s->valid=XW_PF_STATE;s->state=XW_PLAY_PLAYING;return 0;}
static int control(void *c,const struct xw_player_command *r){(void)c;(void)r;commands++;return 1;}
static int close_backend(void *c){(void)c;assert(0);return 0;}
int main(void){
 static struct xw_session_manager m;static struct xw_player backend;static struct xw_player_session_offer offer;
 struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,control,0,close_backend};int delivery[2];
 assert(!xw_sessions_init(&m,17,7)&&!xw_player_bind(&backend,&provider)&&!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 assert(xw_player_session_offer(&offer,&m,&backend,delivery[0],7,1,0)==XW_SESSION_DENIED);
 assert(!xw_player_session_offer(&offer,&m,&backend,delivery[0],3,3,0));
 int client=-1;struct xw_descriptor_offer identity;assert(!xw_service_descriptor_receive(delivery[1],&client,&identity)&&identity.grants==3);
 /* An early playback command must be refused, even on a valid descriptor. */
 struct xw_rpc_request request={0};request.kind=XW_RPC_COMMAND;request.serial=1;request.body.command.operation=XW_OP_NEXT;
 unsigned char frame[XW_RPC_REQUEST_MAX];size_t size;assert(!xw_rpc_encode_request(&request,frame,sizeof frame,&size)&&write(client,frame,size)==(ssize_t)size);
 assert(xw_player_session_offer_tick(&offer,1)==XW_PLAYER_IO&&!offer.channel.bound&&!commands&&backend.initialized);
 close(client);close(delivery[0]);close(delivery[1]);
 static struct xw_player_session_offer idle;assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 assert(!xw_player_session_offer(&idle,&m,&backend,delivery[0],1,1,0));
 assert(xw_player_session_offer_tick(&idle,3000)==XW_PLAYER_IO&&!idle.channel.bound&&!commands);
 close(delivery[0]);close(delivery[1]);
 static struct xw_player_session_offer dribble;assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 assert(!xw_player_session_offer(&dribble,&m,&backend,delivery[0],1,1,0));
 assert(!xw_service_descriptor_receive(delivery[1],&client,&identity));assert(write(client,"a",1)==1);
 assert(!xw_player_session_offer_tick(&dribble,2999)&&dribble.channel.deadline==3000);
 assert(xw_player_session_offer_tick(&dribble,3000)==XW_PLAYER_IO&&!dribble.channel.bound);
 close(client);close(delivery[0]);close(delivery[1]);
 static struct xw_player_session_offer failed;
 assert(xw_player_session_offer(&failed,&m,&backend,-1,1,1,0)==XW_SESSION_INVALID&&!failed.channel.bound&&!failed.player.backend&&backend.initialized);
 puts("Session offer: explicit grant, targeted descriptor, early-command refusal, rollback and fixed adoption deadline passed");return 0;
}
