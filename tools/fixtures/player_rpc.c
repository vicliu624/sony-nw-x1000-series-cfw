/* Actual local sockets and client/server core; modeled player, never a device. */
#define _POSIX_C_SOURCE 200809L
#include "../../runtime/platform/player/rpc_posix.h"
#include "../../runtime/store/deadline.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <poll.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <stddef.h>
#ifdef XW_RPC_HOST_TEST
#include <time.h>
int hb_monotonic_millis(unsigned long long *out){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;*out=(unsigned long long)t.tv_sec*1000u+(unsigned)t.tv_nsec/1000000u;return 0;}
#endif
static struct xw_player_rpc_server server;
static struct xw_player player;
static struct xw_player_remote remote;
static unsigned track=1,stopped,closed;
static unsigned long long pause_until;
static enum xw_play_state state=XW_PLAY_PAUSED;
static void item(struct xw_media_item *out,unsigned i){memset(out,0,sizeof *out);snprintf(out->id.value,sizeof out->id.value,"track:%03u",i);snprintf(out->title,sizeof out->title,"Title %u 猫",i);strcpy(out->artist,"Artist");strcpy(out->album,"Album");out->flags=7;out->duration_ms=100000;}
static int snapshot(void *ctx,struct xw_player_snapshot *out){(void)ctx;memset(out,0,sizeof *out);out->valid=63;out->state=state;item(&out->track,track);out->position_ms=1234;out->duration_ms=100000;out->volume=12;out->volume_max=30;out->library_revision=7;out->queue_revision=8+track;return 0;}
static int command(void *ctx,const struct xw_player_command *c){(void)ctx;if(c->operation==XW_OP_PLAY)state=XW_PLAY_PLAYING;if(c->operation==XW_OP_PAUSE){state=XW_PLAY_PAUSED;if(c->value==-12345)stopped=1;if(c->value==555){assert(!hb_monotonic_millis(&pause_until));pause_until+=200;}}if(c->operation==XW_OP_PREVIOUS&&c->value==444){unsigned long long now;assert(!hb_monotonic_millis(&now));assert(xw_player_rpc_server_tick(&server,now)==XW_PLAYER_BUSY&&xw_player_rpc_server_close(&server)==XW_PLAYER_BUSY);}if(c->operation==XW_OP_NEXT){track++;if(c->value==777)assert(!shutdown(server.peer,SHUT_RDWR));return XW_PLAYER_UNCERTAIN;}return XW_PLAYER_ACCEPTED;}
static int browse(void *ctx,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *out){(void)ctx;memset(out,0,sizeof *out);out->revision=!strcmp(q->container.value,"unknown-revision")?0:q->view==XW_MEDIA_QUEUE?8+track:7;out->offset=q->offset;out->total=q->view==XW_MEDIA_PLAYLISTS?1:16;if(q->expected_revision&&q->expected_revision!=out->revision)return XW_PLAYER_STALE;if(q->offset>out->total)return XW_PLAYER_INVALID;out->count=out->total-q->offset;if(out->count>q->limit)out->count=q->limit;out->next_offset=q->offset+out->count;for(unsigned i=0;i<out->count;i++){item(items+i,q->offset+i+1);if(q->view==XW_MEDIA_PLAYLISTS){strcpy(items[i].id.value,"list:one");strcpy(items[i].title,"Playlist 猫");}}return 0;}
static int close_player(void *ctx){(void)ctx;closed++;return 0;}
static void wire_tests(void){
 struct xw_rpc_request request={0},decoded_request,prior_request;struct xw_rpc_response response,decoded,prior;
 static unsigned char packet[XW_RPC_PACKET_MAX];size_t bytes;request.kind=XW_RPC_COMMAND;request.serial=0x12345678;request.body.command.operation=XW_OP_STEP_VOLUME;request.body.command.value=-1;request.body.command.expected_revision=0x1122334455667788ull;
 assert(!xw_rpc_encode_request(&request,packet,sizeof packet,&bytes)&&bytes==166);assert(packet[0]=='X'&&packet[1]=='W'&&packet[2]=='P'&&packet[3]=='1');assert(packet[158]==0x88&&packet[165]==0x11);
 assert(!xw_rpc_decode_request(packet,bytes,&decoded_request)&&decoded_request.body.command.value==-1&&decoded_request.body.command.expected_revision==request.body.command.expected_revision);
 memset(&decoded_request,0x5a,sizeof decoded_request);prior_request=decoded_request;packet[20]=255;assert(xw_rpc_decode_request(packet,bytes,&decoded_request)==XW_PLAYER_PROTOCOL&&!memcmp(&decoded_request,&prior_request,sizeof decoded_request));
 memset(&response,0,sizeof response);response.kind=XW_RPC_SNAPSHOT;response.serial=7;response.body.snapshot.valid=63;response.body.snapshot.state=XW_PLAY_PLAYING;item(&response.body.snapshot.track,1);memset(response.body.snapshot.track.title,0xa5,256);memcpy(response.body.snapshot.track.title,"Safe\0",5);response.body.snapshot.volume_min=-2;response.body.snapshot.volume=1;response.body.snapshot.volume_max=30;
 assert(!xw_rpc_encode_response(&response,packet,sizeof packet,&bytes)&&bytes==909);assert(packet[24+8+65+5]==0);assert(!xw_rpc_decode_response(packet,bytes,&decoded)&&decoded.body.snapshot.volume_min==-2&&!strcmp(decoded.body.snapshot.track.title,"Safe"));
 memset(&decoded,0x5a,sizeof decoded);prior=decoded;assert(xw_rpc_decode_response(packet,bytes-1,&decoded)==XW_PLAYER_PROTOCOL&&!memcmp(&decoded,&prior,sizeof decoded));
 memset(&response,0,sizeof response);response.kind=XW_RPC_BROWSE;response.serial=8;response.body.browse.page.count=16;response.body.browse.page.total=16;response.body.browse.page.next_offset=16;response.body.browse.page.revision=9;for(unsigned i=0;i<16;i++)item(response.body.browse.items+i,i+1);
 assert(!xw_rpc_encode_response(&response,packet,sizeof packet,&bytes)&&bytes==XW_RPC_PACKET_MAX);assert(!xw_rpc_decode_response(packet,bytes,&decoded)&&decoded.body.browse.page.count==16&&!strcmp(decoded.body.browse.items[15].id.value,"track:016"));packet[36]=255;assert(xw_rpc_decode_response(packet,bytes,&decoded)==XW_PLAYER_PROTOCOL);
 memset(&response,0,sizeof response);response.kind=XW_RPC_SNAPSHOT;response.serial=9;response.body.snapshot.state=XW_PLAY_PAUSED;
 assert(!xw_rpc_encode_response(&response,packet,sizeof packet,&bytes));
 struct xw_rpc_response saved_response;memset(&decoded,0x5a,sizeof decoded);saved_response=decoded;packet[28]=255;
 assert(xw_rpc_decode_response(packet,bytes,&decoded)==XW_PLAYER_PROTOCOL&&!memcmp(&decoded,&saved_response,sizeof decoded));
 packet[28]=XW_PLAY_PAUSED;
 union {struct xw_rpc_response response;unsigned char packet[XW_RPC_PACKET_MAX];} overlapping;
 memcpy(overlapping.packet,packet,bytes);assert(xw_rpc_decode_response(overlapping.packet,bytes,&overlapping.response)==XW_PLAYER_INVALID&&!memcmp(overlapping.packet,packet,bytes));
 puts("Wire: explicit fields, signed values, revision, canonical tails, atomic rejection and maximum page passed");
}
static void bad_frame(const char *endpoint){struct sockaddr_un a;memset(&a,0,sizeof a);a.sun_family=AF_UNIX;memcpy(a.sun_path+1,endpoint,strlen(endpoint));int fd=socket(AF_UNIX,SOCK_STREAM,0);assert(fd>=0);assert(!connect(fd,(struct sockaddr *)&a,(socklen_t)(offsetof(struct sockaddr_un,sun_path)+1+strlen(endpoint))));unsigned char bad[20]={0};assert(send(fd,bad,sizeof bad,MSG_NOSIGNAL)==20);close(fd);}
static void abandoned_command(const char *endpoint){struct sockaddr_un a;memset(&a,0,sizeof a);a.sun_family=AF_UNIX;memcpy(a.sun_path+1,endpoint,strlen(endpoint));int fd=socket(AF_UNIX,SOCK_STREAM,0);assert(fd>=0);assert(!connect(fd,(struct sockaddr *)&a,(socklen_t)(offsetof(struct sockaddr_un,sun_path)+1+strlen(endpoint))));struct xw_rpc_request request={0};request.kind=XW_RPC_COMMAND;request.serial=42;request.body.command.operation=XW_OP_NEXT;unsigned char packet[XW_RPC_REQUEST_MAX];size_t n;assert(!xw_rpc_encode_request(&request,packet,sizeof packet,&n));assert(send(fd,packet,n,MSG_NOSIGNAL)==(ssize_t)n);assert(!shutdown(fd,SHUT_RDWR));close(fd);}
static int run_server(const char *endpoint){
 struct xw_player_provider provider={XW_PLAYER_API,(1u<<XW_OP_PLAY)|(1u<<XW_OP_PAUSE)|(1u<<XW_OP_NEXT)|(1u<<XW_OP_PREVIOUS),0,snapshot,command,browse,close_player};assert(!xw_player_bind(&player,&provider));assert(!xw_player_rpc_server_open(&server,&player,endpoint));puts("READY");fflush(stdout);
 unsigned long long start,now;assert(!hb_monotonic_millis(&start));
 while(!stopped||server.peer>=0){assert(!hb_monotonic_millis(&now)&&now-start<20000);if(now<pause_until){poll(0,0,1);continue;}int rc=xw_player_rpc_server_tick(&server,now);assert(rc==0||rc==1||rc==XW_PLAYER_PROTOCOL||rc==XW_PLAYER_IO);poll(0,0,1);}
 assert(!xw_player_rpc_server_close(&server)&&player.initialized&&!closed);assert(!xw_player_close(&player)&&closed==1);puts("Server cleanup passed");return 0;
}
static int run_client(const char *endpoint){
 volatile int stop=0;assert(!xw_player_remote_bind(&player,&remote,endpoint,1500,&stop));struct xw_player_snapshot out;uint32_t changes;
 assert(!xw_player_poll(&player,&out,&changes)&&out.state==XW_PLAY_PAUSED&&!strcmp(out.track.id.value,"track:001"));assert(!xw_player_poll(&player,&out,&changes)&&!changes);
 struct xw_player_command c={0};c.operation=XW_OP_PLAY;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED&&out.state==XW_PLAY_PAUSED);assert(!xw_player_poll(&player,&out,&changes)&&out.state==XW_PLAY_PLAYING&&changes==XW_PC_STATE);
 c.operation=XW_OP_NEXT;assert(xw_player_command(&player,&c)==XW_PLAYER_UNCERTAIN);assert(!xw_player_poll(&player,&out,&changes)&&!strcmp(out.track.id.value,"track:002"));
 c.value=777;assert(xw_player_command(&player,&c)==XW_PLAYER_UNCERTAIN);assert(!xw_player_poll(&player,&out,&changes)&&!strcmp(out.track.id.value,"track:003"));
 c.operation=XW_OP_PREVIOUS;c.value=444;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED);
 c.operation=XW_OP_PAUSE;c.value=555;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED);remote.timeout_ms=15;c.operation=XW_OP_NEXT;c.value=0;assert(xw_player_command(&player,&c)==XW_PLAYER_UNCERTAIN);remote.timeout_ms=1500;abandoned_command(endpoint);assert(!xw_player_poll(&player,&out,&changes)&&!strcmp(out.track.id.value,"track:003"));
 struct xw_media_query q={0};struct xw_media_item rows[16],saved[16];struct xw_media_page page,previous;
 q.view=XW_MEDIA_TRACKS;q.limit=16;assert(!xw_media_browse(&player,&q,rows,16,&page)&&page.count==16&&!strcmp(rows[15].id.value,"track:016"));
 strcpy(q.container.value,"unknown-revision");assert(!xw_media_browse(&player,&q,rows,16,&page)&&page.revision==0);q.expected_revision=7;assert(xw_media_browse(&player,&q,rows,16,&page)==XW_PLAYER_STALE);q.expected_revision=0;q.container.value[0]=0;
 q.view=XW_MEDIA_PLAYLISTS;assert(!xw_media_browse(&player,&q,rows,16,&page)&&page.count==1&&!strcmp(rows[0].id.value,"list:one"));
 q.view=XW_MEDIA_PLAYLIST_TRACKS;strcpy(q.container.value,"list:one");assert(!xw_media_browse(&player,&q,rows,16,&page)&&page.count==16);
 q.view=XW_MEDIA_QUEUE;q.expected_revision=1;memcpy(saved,rows,sizeof rows);previous=page;assert(xw_media_browse(&player,&q,rows,16,&page)==XW_PLAYER_STALE&&!memcmp(rows,saved,sizeof rows)&&!memcmp(&page,&previous,sizeof page));
 bad_frame(endpoint);assert(!xw_player_poll(&player,&out,&changes)&&!strcmp(out.track.id.value,"track:003"));
 stop=1;assert(xw_player_command(&player,&c)==XW_PLAYER_UNAVAILABLE);stop=0;assert(!xw_player_poll(&player,&out,&changes)&&!strcmp(out.track.id.value,"track:003"));
 assert(!xw_player_close(&player));assert(!xw_player_remote_bind(&player,&remote,endpoint,1500,&stop));c.operation=XW_OP_PAUSE;c.value=-12345;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED);assert(!xw_player_close(&player));
 puts("RPC: controls, no retry, snapshots, maximum pages, stale/cancelled output, abandoned-frame refusal, reentry and malformed peer recovery passed");return 0;
}
int main(int argc,char **argv){if(argc==1){wire_tests();return 0;}if(argc!=3)return 64;if(!strcmp(argv[1],"--server"))return run_server(argv[2]);if(!strcmp(argv[1],"--client"))return run_client(argv[2]);return 64;}
