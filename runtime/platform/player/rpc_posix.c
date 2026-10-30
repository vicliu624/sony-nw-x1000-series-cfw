#include "rpc_posix.h"
#include "../../store/deadline.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stddef.h>
#include <string.h>
extern unsigned long pthread_self(void);
/* Modern ARM headers redirect even these scalar-only operations to time64
 * adapters. Bind the stock ABI explicitly; no flock/timeval option is used. */
extern int xw_rpc_fcntl(int,int,...) __asm__("fcntl");
extern int xw_rpc_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
typedef char socket_word_layout[(sizeof(socklen_t)==4&&sizeof(struct pollfd)==8)?1:-1];
#define SERVER_BOUND 0x58575253u
#define REMOTE_BOUND 0x58575243u
#define PEER_TIMEOUT 3000u
#define IO_CHUNK 2048u

static int address(const char *name,struct sockaddr_un *out,socklen_t *length){
 if(!name)return XW_PLAYER_INVALID;unsigned n=0;
 while(n<95&&name[n]){if((unsigned char)name[n]<33||(unsigned char)name[n]>126)return XW_PLAYER_INVALID;n++;}
 if(!n||n==95)return XW_PLAYER_INVALID;
 memset(out,0,sizeof *out);out->sun_family=AF_UNIX;memcpy(out->sun_path+1,name,n);
 *length=(socklen_t)(offsetof(struct sockaddr_un,sun_path)+1+n);return 0;
}
static int nonblocking(int fd){int flags=xw_rpc_fcntl(fd,F_GETFL);return flags<0||xw_rpc_fcntl(fd,F_SETFL,flags|O_NONBLOCK)<0||xw_rpc_fcntl(fd,F_SETFD,FD_CLOEXEC)<0?-1:0;}
static int transient(void){return errno==EINTR||errno==EAGAIN||errno==EWOULDBLOCK;}
static void drop_peer(struct xw_player_rpc_server *s){if(s->peer>=0)close(s->peer);s->peer=-1;s->received=s->expected=s->sent=s->total=0;}
int xw_player_rpc_server_open(struct xw_player_rpc_server *s,struct xw_player *player,const char *endpoint){
 struct sockaddr_un addr;socklen_t length;int rc;
 if(!s||!player)return XW_PLAYER_INVALID;if(s->bound)return XW_PLAYER_BUSY;if(!player->initialized)return XW_PLAYER_CLOSED;
 if((rc=address(endpoint,&addr,&length)))return rc;
 memset(s,0,sizeof *s);s->listener=s->peer=-1;
 int fd=socket(AF_UNIX,SOCK_STREAM,0);if(fd<0)return XW_PLAYER_UNAVAILABLE;
 if(nonblocking(fd)||bind(fd,(struct sockaddr *)&addr,length)||listen(fd,4)){rc=errno==EADDRINUSE?XW_PLAYER_BUSY:XW_PLAYER_IO;close(fd);return rc;}
 s->listener=fd;s->player=player;s->owner=pthread_self();s->bound=SERVER_BOUND;return 0;
}
static int execute(struct xw_player_rpc_server *s){
 struct xw_rpc_request request;int rc=xw_rpc_decode_request(s->input,s->received,&request);if(rc)return rc;
 struct xw_rpc_response *response=&s->response;memset(response,0,sizeof *response);response->kind=request.kind;response->serial=request.serial;
 switch(request.kind){
 case XW_RPC_HELLO:response->body.commands=s->player->provider.commands;break;
 case XW_RPC_COMMAND:response->result=xw_player_command(s->player,&request.body.command);break;
 case XW_RPC_SNAPSHOT:response->result=xw_player_snapshot(s->player,&response->body.snapshot);break;
 case XW_RPC_BROWSE:response->result=xw_media_browse(s->player,&request.body.query,response->body.browse.items,XW_MEDIA_PAGE_MAX,&response->body.browse.page);break;
 default:return XW_PLAYER_PROTOCOL;
 }
 rc=xw_rpc_encode_response(response,s->output,sizeof s->output,&s->total);if(rc)return rc;
 return 0;
}
static int server_tick(struct xw_player_rpc_server *s,unsigned long long now){
 if(!s||s->bound!=SERVER_BOUND)return XW_PLAYER_CLOSED;if(s->owner!=pthread_self())return XW_PLAYER_BUSY;
 if(now<s->last){drop_peer(s);s->last=now;return XW_PLAYER_IO;}s->last=now;
 if(s->peer>=0&&now>=s->deadline)drop_peer(s);
 if(s->peer<0){int fd=accept(s->listener,0,0);if(fd<0)return transient()?0:XW_PLAYER_IO;if(nonblocking(fd)){close(fd);return XW_PLAYER_IO;}s->peer=fd;s->deadline=now+PEER_TIMEOUT;s->expected=20;}
 if(!s->total){
  if(s->received<s->expected){
  size_t left=s->expected-s->received;ssize_t n=recv(s->peer,s->input+s->received,left,0);
  if(n<=0){if(n<0&&transient())return 0;drop_peer(s);return XW_PLAYER_IO;}
  s->received+=(size_t)n;
  if(s->received==20&&s->expected==20){unsigned reply=0;uint32_t kind=0,serial=0,bytes=0;int rc=xw_rpc_header(s->input,&reply,&kind,&serial,&bytes);
   unsigned expected=kind==XW_RPC_COMMAND?146:kind==XW_RPC_BROWSE?85:0;
   if(rc||reply||bytes!=expected||20u+bytes>sizeof s->input){drop_peer(s);return XW_PLAYER_PROTOCOL;}s->expected=20u+bytes;
  }
  }
  if(s->received!=s->expected)return 0;
  /* A timed-out client can leave a complete frame queued while Sony is not
   * pumping. Do not execute it after the peer has already closed/half-closed.
   * One exchange per connection also means pipelined bytes are invalid. */
  unsigned char extra;ssize_t peek=recv(s->peer,&extra,1,MSG_PEEK);
  if(peek==0){drop_peer(s);return XW_PLAYER_IO;}
  if(peek>0){drop_peer(s);return XW_PLAYER_PROTOCOL;}
  if(errno==EINTR)return 0;
  if(errno!=EAGAIN&&errno!=EWOULDBLOCK){drop_peer(s);return XW_PLAYER_IO;}
  int rc=execute(s);if(rc){drop_peer(s);return rc;}
 }
 size_t left=s->total-s->sent;if(left>IO_CHUNK)left=IO_CHUNK;
 ssize_t n=send(s->peer,s->output+s->sent,left,MSG_NOSIGNAL);
 if(n<=0){if(n<0&&transient())return 0;drop_peer(s);return XW_PLAYER_IO;}
 s->sent+=(size_t)n;if(s->sent==s->total)drop_peer(s);return XW_PLAYER_ACCEPTED;
}
int xw_player_rpc_server_tick(struct xw_player_rpc_server *s,unsigned long long now){
 if(!s||s->bound!=SERVER_BOUND)return XW_PLAYER_CLOSED;
 if(s->busy||s->owner!=pthread_self())return XW_PLAYER_BUSY;
 s->busy=1;int rc=server_tick(s,now);s->busy=0;return rc;
}
int xw_player_rpc_server_close(struct xw_player_rpc_server *s){
 if(!s||s->bound!=SERVER_BOUND)return XW_PLAYER_CLOSED;if(s->busy||s->owner!=pthread_self())return XW_PLAYER_BUSY;
 drop_peer(s);close(s->listener);memset(s,0,sizeof *s);s->listener=s->peer=-1;return 0;
}

struct rpc_deadline {unsigned long long end,last;};
static int begin(struct rpc_deadline *d,unsigned timeout){unsigned long long now;if(hb_monotonic_millis(&now))return XW_PLAYER_IO;d->last=now;d->end=now+timeout;return 0;}
static int wait_fd(int fd,short events,struct rpc_deadline *d,volatile int *stop){
 for(;;){unsigned long long now;if(stop&&*stop)return XW_PLAYER_UNAVAILABLE;if(hb_monotonic_millis(&now)||now<d->last)return XW_PLAYER_IO;d->last=now;if(now>=d->end)return XW_PLAYER_UNAVAILABLE;
  unsigned long long remaining=d->end-now;int ms=remaining>100?100:(int)remaining;struct pollfd descriptor={fd,events,0};int rc=poll(&descriptor,1,ms);
  if(rc<0){if(errno==EINTR)continue;return XW_PLAYER_IO;}if(rc>0){if(descriptor.revents&(POLLERR|POLLNVAL))return XW_PLAYER_IO;if(descriptor.revents&(events|POLLHUP))return 0;}
 }
}
static int exchange(struct xw_player_remote *remote,struct xw_rpc_request *request,struct xw_rpc_response *response){
 unsigned char input[XW_RPC_REQUEST_MAX];size_t bytes=0,sent=0,received=0,expected=20;int rc,fd=-1;struct rpc_deadline deadline;struct sockaddr_un addr;socklen_t length;
 if(remote->stop&&*remote->stop)return XW_PLAYER_UNAVAILABLE;
 request->serial=++remote->serial;if(!request->serial)request->serial=++remote->serial;
 if((rc=xw_rpc_encode_request(request,input,sizeof input,&bytes))||(rc=address(remote->endpoint,&addr,&length))||(rc=begin(&deadline,remote->timeout_ms)))return rc;
 fd=socket(AF_UNIX,SOCK_STREAM,0);if(fd<0)return XW_PLAYER_UNAVAILABLE;if(nonblocking(fd)){rc=XW_PLAYER_IO;goto done;}
 if(connect(fd,(struct sockaddr *)&addr,length)){
  if(errno!=EINPROGRESS){rc=errno==EAGAIN?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;goto done;}
  if((rc=wait_fd(fd,POLLOUT,&deadline,remote->stop)))goto done;
  int error=0;socklen_t size=sizeof error;if(xw_rpc_getsockopt(fd,SOL_SOCKET,SO_ERROR,&error,&size)||error){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 }
 while(sent<bytes){if((rc=wait_fd(fd,POLLOUT,&deadline,remote->stop)))goto done;ssize_t n=send(fd,input+sent,bytes-sent,MSG_NOSIGNAL);if(n<0&&transient())continue;if(n<=0){rc=XW_PLAYER_IO;goto done;}sent+=(size_t)n;}
 while(received<expected){if((rc=wait_fd(fd,POLLIN,&deadline,remote->stop)))goto done;ssize_t n=recv(fd,remote->packet+received,expected-received,0);if(n<0&&transient())continue;if(n<=0){rc=XW_PLAYER_IO;goto done;}received+=(size_t)n;
  if(received==20&&expected==20){unsigned reply;uint32_t kind,serial,body;rc=xw_rpc_header(remote->packet,&reply,&kind,&serial,&body);if(rc||!reply||kind!=request->kind||serial!=request->serial||body<4){rc=XW_PLAYER_PROTOCOL;goto done;}expected=20u+body;}
 }
 rc=xw_rpc_decode_response(remote->packet,received,response);
done:
 if(fd>=0)close(fd);
 /* A lost/malformed reply cannot prove that a sent command did not execute.
  * Never reconnect or replay a non-idempotent command here. */
 return rc&&sent&&request->kind==XW_RPC_COMMAND?XW_PLAYER_UNCERTAIN:rc;
}
static int remote_snapshot(void *context,struct xw_player_snapshot *out){struct xw_player_remote *r=context;struct xw_rpc_request request={0};struct xw_rpc_response *response=&r->response;if(r->bound!=REMOTE_BOUND)return XW_PLAYER_CLOSED;request.kind=XW_RPC_SNAPSHOT;int rc=exchange(r,&request,response);if(rc)return rc;if(response->result)return response->result;*out=response->body.snapshot;return 0;}
static int remote_command(void *context,const struct xw_player_command *command){struct xw_player_remote *r=context;struct xw_rpc_request request={0};struct xw_rpc_response *response=&r->response;if(r->bound!=REMOTE_BOUND)return XW_PLAYER_CLOSED;request.kind=XW_RPC_COMMAND;request.body.command=*command;int rc=exchange(r,&request,response);return rc?rc:response->result;}
static int remote_browse(void *context,const struct xw_media_query *query,struct xw_media_item *items,struct xw_media_page *page){struct xw_player_remote *r=context;struct xw_rpc_request request={0};struct xw_rpc_response *response=&r->response;if(r->bound!=REMOTE_BOUND)return XW_PLAYER_CLOSED;request.kind=XW_RPC_BROWSE;request.body.query=*query;int rc=exchange(r,&request,response);if(rc)return rc;if(response->result)return response->result;memcpy(items,response->body.browse.items,response->body.browse.page.count*sizeof *items);*page=response->body.browse.page;return 0;}
static int remote_close(void *context){struct xw_player_remote *r=context;memset(r,0,sizeof *r);return 0;}
int xw_player_remote_bind(struct xw_player *player,struct xw_player_remote *remote,const char *endpoint,unsigned timeout,volatile int *stop){
 struct sockaddr_un addr;socklen_t length;int rc;if(!player||!remote||!timeout||timeout>5000)return XW_PLAYER_INVALID;if(player->initialized||remote->bound)return XW_PLAYER_BUSY;
 if((rc=address(endpoint,&addr,&length)))return rc;memset(remote,0,sizeof *remote);memcpy(remote->endpoint,endpoint,strlen(endpoint)+1);remote->timeout_ms=timeout;remote->stop=stop;
 struct xw_rpc_request request={0};struct xw_rpc_response *response=&remote->response;request.kind=XW_RPC_HELLO;
 if((rc=exchange(remote,&request,response)))return rc;if(response->result)return response->result;
 struct xw_player_provider provider={0};provider.api=XW_PLAYER_API;provider.commands=response->body.commands;provider.context=remote;provider.snapshot=remote_snapshot;provider.command=remote_command;provider.browse=remote_browse;provider.close=remote_close;
 remote->bound=REMOTE_BOUND;rc=xw_player_bind(player,&provider);if(rc)remote_close(remote);return rc;
}
