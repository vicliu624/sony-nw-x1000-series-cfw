#include "managed_channel.h"
#include "managed_control.h"
#include <sys/socket.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
extern int channel_fcntl(int,int,...) __asm__("fcntl");
static int transient(void){return errno==EINTR||errno==EAGAIN||errno==EWOULDBLOCK;}
int xw_managed_channel_open(struct xw_managed_channel *s,struct xw_managed_player *p,int fd,uint64_t now){
 if(!s||s->bound||!p||!p->backend||fd<0||now>UINT64_MAX-3000)return XW_PLAYER_INVALID;
 int flags=channel_fcntl(fd,F_GETFL);if(flags<0||channel_fcntl(fd,F_SETFD,FD_CLOEXEC)||channel_fcntl(fd,F_SETFL,flags|O_NONBLOCK))return XW_PLAYER_IO;
 memset(s,0,sizeof *s);s->player=p;s->fd=fd;s->bound=1;s->last=now;s->deadline=now+3000;s->expected=XW_RPC_HEADER_BYTES;return 0;
}
int xw_managed_channel_close(struct xw_managed_channel *s){
 if(!s||!s->bound)return XW_PLAYER_CLOSED;
 if(!s->closing){s->closing=1;close(s->fd);s->fd=-1;
  if(!s->player->backend){struct xw_session_snapshot state;if(!xw_session_close_query(s->player->manager,s->player->requests.session,&state)&&state.state==XW_SESSION_CLOSED){s->bound=0;return 1;}return XW_PLAYER_IO;}
  int rc=xw_session_revoke(s->player->manager,s->player->requests.session,XW_SESSION_CLIENT_LOST);if(rc<0)return XW_PLAYER_IO;}
 int rc=xw_managed_player_close(s->player);if(rc)return rc;s->bound=0;return 1;
}
static int failed(struct xw_managed_channel *s){int rc=xw_managed_channel_close(s);return rc==1?XW_PLAYER_IO:rc;}
int xw_managed_channel_tick(struct xw_managed_channel *s,uint64_t now){
 if(!s||!s->bound)return XW_PLAYER_CLOSED;if(s->closing)return xw_managed_channel_close(s);
 if(now<s->last||now>UINT64_MAX-3000)return failed(s);s->last=now;
 if((!s->hello||s->received)&&now>=s->deadline)return failed(s);
 if(!s->total){
  for(unsigned pass=0;pass<2&&s->received<s->expected;pass++){
   ssize_t n=recv(s->fd,s->input+s->received,s->expected-s->received,MSG_DONTWAIT);
   if(n<0)return transient()?0:failed(s);if(!n)return xw_managed_channel_close(s);
   if(!s->received&&s->hello)s->deadline=now+3000;s->received+=(size_t)n;
   if(s->received==XW_RPC_HEADER_BYTES&&s->expected==XW_RPC_HEADER_BYTES){
    if(!memcmp(s->input,"XLC1",4)){s->expected=XW_CONTROL_REQUEST_BYTES;continue;}
    unsigned reply;uint32_t kind,serial,body;
    if(xw_rpc_header(s->input,&reply,&kind,&serial,&body)||reply||body>sizeof s->input-XW_RPC_HEADER_BYTES)return failed(s);
    s->expected=XW_RPC_HEADER_BYTES+body;
   }
  }
  if(s->received<s->expected)return 0;
  unsigned char byte;ssize_t peek=recv(s->fd,&byte,1,MSG_PEEK|MSG_DONTWAIT);
  if(!peek)return xw_managed_channel_close(s);if(peek<0&&!transient())return failed(s);
  if(!s->hello){struct xw_rpc_request initial;if(xw_rpc_decode_request(s->input,s->received,&initial)||initial.kind!=XW_RPC_HELLO)return failed(s);}
  if(!memcmp(s->input,"XLC1",4)){
   int sync=s->input[4]==XW_CONTROL_SNAPSHOT_SYNC&&!s->input[5]&&!s->input[6]&&!s->input[7];
   int rc=sync?xw_managed_sync_execute(s->player,s->input,s->received,s->output,sizeof s->output,&s->total,&s->response):xw_managed_control_execute(s->player,s->input,s->received,s->output,sizeof s->output,&s->total);
   if(rc)return failed(s);
  }else if(xw_managed_rpc_execute(s->player,s->input,s->received,&s->response)||xw_rpc_encode_response(&s->response,s->output,sizeof s->output,&s->total))return failed(s);
  if(!s->hello){if(s->response.result)return failed(s);s->hello=1;}
 }
 size_t bytes=s->total-s->sent;if(bytes>2048)bytes=2048;
 ssize_t n=send(s->fd,s->output+s->sent,bytes,MSG_DONTWAIT|MSG_NOSIGNAL);
 if(n<0)return transient()?0:failed(s);if(!n)return failed(s);s->sent+=(size_t)n;
 if(s->sent==s->total){s->received=s->sent=s->total=0;s->expected=XW_RPC_HEADER_BYTES;}
 return 0;
}
