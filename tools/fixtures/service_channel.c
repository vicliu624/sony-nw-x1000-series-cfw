/* Isolated inherited-channel fixture, not a production listener. */
#include "../../runtime/platform/player/managed_rpc.h"
#include "../../runtime/platform/player/managed_channel.h"
#include "../../runtime/platform/player/managed_remote.h"
#include "../../runtime/platform/player/managed_client.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>
#include <errno.h>
static unsigned controls;
static unsigned char packet[XW_RPC_PACKET_MAX];
static void write_all(int fd,const void *data,size_t size){
 const unsigned char *p=data;size_t n=0;
 while(n<size){ssize_t r=write(fd,p+n,size-n);if(r<0&&errno==EINTR)continue;assert(r>0);n+=(size_t)r;}
}
static int state(void *c,struct xw_player_snapshot *s){(void)c;s->valid=XW_PF_STATE;s->state=XW_PLAY_PLAYING;return 0;}
static int command(void *c,const struct xw_player_command *r){(void)c;(void)r;controls++;return XW_PLAYER_ACCEPTED;}
static int backend_close(void *c){(void)c;assert(0);return 0;}
static int browse(void *c,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 (void)c;memset(items,0,sizeof *items);strcpy(items->id.value,"model:42");strcpy(items->title,"Channel song");items->flags=XW_MEDIA_TITLE_PRESENT;
 page->offset=q->offset;page->count=1;page->next_offset=q->offset+1;page->total=page->next_offset;return 0;
}
static struct xw_managed_remote remote;
static uint64_t clock_ticks;
static int test_clock(void *context,uint64_t *out){(void)context;*out=clock_ticks++;return 0;}
int main(int argc,char **argv){
 int sockets[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,sockets));
 pid_t child=fork();assert(child>=0);
 if(!child){
  close(sockets[0]);
  if(argc>1){assert(dup2(sockets[1],3)==3);if(sockets[1]!=3)close(sockets[1]);execvp(argv[1],argv+1);_exit(127);}
  static struct xw_managed_client client;static struct xw_player player;
  assert(!xw_managed_client_bind_stock(&player,&client,sockets[1],23,3000,0));
  struct xw_player_command next={0};next.operation=XW_OP_NEXT;
  assert(xw_player_command(&player,&next)==XW_PLAYER_ACCEPTED);
  struct xw_player_snapshot observed;assert(!xw_player_snapshot(&player,&observed)&&observed.state==XW_PLAY_PLAYING);
  struct xw_media_query query={0};query.limit=1;struct xw_media_item item;struct xw_media_page page;
  assert(!xw_media_browse(&player,&query,&item,1,&page)&&page.count==1&&!strcmp(item.title,"Channel song"));
  uint64_t sequence,cursor;assert(!xw_managed_client_sync(&client,&observed,&sequence)&&sequence==1);
  struct xw_service_event events[16];uint32_t count;
  assert(!xw_managed_client_events(&client,sequence,16,events,16,&count,&cursor)&&!count&&cursor==sequence);
  struct xw_session_snapshot receipt;
  assert(!xw_managed_client_status(&client,&receipt)&&receipt.state==XW_SESSION_ACTIVE);
  assert(!xw_managed_client_end(&client,&receipt)&&receipt.state==XW_SESSION_CLOSED);
  assert(!xw_player_close(&player));_exit(0);
 }
 close(sockets[1]);static struct xw_session_manager m;static struct xw_player backend;static struct xw_managed_player p;
 struct xw_session_handle h;struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,state,command,browse,backend_close};
 assert(!xw_sessions_init(&m,23,7)&&!xw_session_open(&m,7,7,&h)&&!xw_player_bind(&backend,&provider)&&!xw_managed_player_bind(&p,&m,h,&backend));
 static struct xw_managed_channel channel;assert(!xw_managed_channel_open(&channel,&p,sockets[0],0));
 for(uint64_t tick=0;channel.bound&&tick<100000;tick++){
  int rc=xw_managed_channel_tick(&channel,tick);assert(rc==0||rc==1);
  extern int poll(void *,unsigned long,int);poll(0,0,1);
 }
 assert(!channel.bound&&backend.initialized&&controls==1);
 struct xw_session_snapshot receipt;assert(!xw_session_close_query(&m,h,&receipt)&&receipt.state==XW_SESSION_CLOSED&&receipt.reason==XW_SESSION_CLIENT_CLOSE);
 int status;assert(waitpid(child,&status,0)==child&&status==0);
 int partial[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,partial));
 static struct xw_managed_player second;static struct xw_managed_channel slow;
 assert(!xw_session_open(&m,7,7,&h)&&!xw_managed_player_bind(&second,&m,h,&backend));
 assert(!xw_managed_channel_open(&slow,&second,partial[0],0));
 write_all(partial[1],"abc",3);assert(!xw_managed_channel_tick(&slow,0)&&slow.received==3);
 assert(xw_managed_channel_tick(&slow,3000)==XW_PLAYER_IO&&!slow.bound&&controls==1&&backend.initialized);
 close(partial[1]);
 int silent[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,silent));
 assert(!xw_managed_remote_adopt(&remote,silent[0],3,0,0,test_clock));
 struct xw_rpc_request lost={0};lost.kind=XW_RPC_COMMAND;lost.serial=1;lost.body.command.operation=XW_OP_NEXT;size_t bytes;
 assert(!xw_rpc_encode_request(&lost,packet,sizeof packet,&bytes));
 assert(xw_managed_remote_exchange(&remote,packet,bytes)==XW_PLAYER_UNCERTAIN&&!remote.bound&&!remote.reply_bytes);
 assert(xw_managed_remote_exchange(&remote,packet,bytes)==XW_PLAYER_CLOSED);close(silent[1]);
 int unresponsive[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,unresponsive));
 static struct xw_managed_client timeout_client;static struct xw_player timeout_player;
 assert(xw_managed_client_bind_stock(&timeout_player,&timeout_client,unresponsive[0],23,3,0)==XW_PLAYER_UNAVAILABLE);
 assert(!timeout_client.remote.bound&&!timeout_player.initialized);close(unresponsive[1]);
 puts("Inherited channel: separate client/server, one control, state/media replies and EOF session release passed");return 0;
}
