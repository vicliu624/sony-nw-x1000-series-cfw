#include "managed_client.h"
#include "provider.h"
#include <string.h>
static int legacy(struct xw_managed_client *c,struct xw_rpc_request *request){
 if(!c||!c->remote.bound)return XW_PLAYER_CLOSED;
 if(c->remote.busy)return XW_PLAYER_BUSY;
 if(c->serial==UINT32_MAX)return XW_PLAYER_UNAVAILABLE;
 request->serial=++c->serial;unsigned char frame[XW_RPC_REQUEST_MAX];size_t bytes;
 int rc=xw_rpc_encode_request(request,frame,sizeof frame,&bytes);if(rc)return rc;
 rc=xw_managed_remote_exchange(&c->remote,frame,bytes);if(rc)return rc;
 rc=xw_rpc_decode_response(c->remote.reply,c->remote.reply_bytes,&c->response);
 if(rc){xw_managed_remote_detach(&c->remote);return request->kind==XW_RPC_COMMAND?XW_PLAYER_UNCERTAIN:rc;}
 return c->response.result;
}
static int snapshot(void *context,struct xw_player_snapshot *out){
 struct xw_managed_client *c=context;struct xw_rpc_request r={0};r.kind=XW_RPC_SNAPSHOT;
 int rc=legacy(c,&r);if(!rc)*out=c->response.body.snapshot;return rc;
}
static int command(void *context,const struct xw_player_command *command){
 struct xw_rpc_request r={0};r.kind=XW_RPC_COMMAND;r.body.command=*command;return legacy(context,&r);
}
static int browse(void *context,const struct xw_media_query *query,struct xw_media_item *items,struct xw_media_page *page){
 struct xw_managed_client *c=context;struct xw_rpc_request r={0};r.kind=XW_RPC_BROWSE;r.body.query=*query;
 int rc=legacy(c,&r);if(!rc){memcpy(items,c->response.body.browse.items,c->response.body.browse.page.count*sizeof *items);*page=c->response.body.browse.page;}return rc;
}
static int detach(void *context){struct xw_managed_client *c=context;return c->remote.bound?xw_managed_remote_detach(&c->remote):0;}
int xw_managed_client_bind(struct xw_player *p,struct xw_managed_client *c,int fd,uint64_t generation,unsigned timeout,volatile int *stop,void *clock_context,int (*clock)(void *,uint64_t *)){
 if(!p||p->initialized||!c||c->used||!generation)return XW_PLAYER_INVALID;
 int rc=xw_managed_remote_adopt(&c->remote,fd,timeout,stop,clock_context,clock);if(rc)return rc;
 c->used=1;c->generation=generation;struct xw_rpc_request hello={0};hello.kind=XW_RPC_HELLO;
 rc=legacy(c,&hello);if(rc){detach(c);return rc;}
 struct xw_player_provider provider={XW_PLAYER_API,c->response.body.commands,c,snapshot,command,browse,detach};
 rc=xw_player_bind(p,&provider);if(rc)detach(c);return rc;
}
static int control(struct xw_managed_client *c,uint32_t op,uint64_t after,uint32_t limit){
 if(!c||!c->remote.bound)return XW_PLAYER_CLOSED;
 if(c->remote.busy)return XW_PLAYER_BUSY;
 if(c->correlation==UINT64_MAX)return XW_PLAYER_UNAVAILABLE;
 unsigned char frame[40];int rc=xw_control_request_encode(op,++c->correlation,c->generation,after,limit,frame,sizeof frame);if(rc)return rc;
 return xw_managed_remote_exchange(&c->remote,frame,sizeof frame);
}
int xw_managed_client_status(struct xw_managed_client *c,struct xw_session_snapshot *out){
 if(!out)return XW_PLAYER_INVALID;int rc=control(c,XW_CONTROL_STATUS,0,0);if(rc)return rc;
 return xw_control_status_decode(c->remote.reply,c->remote.reply_bytes,XW_CONTROL_STATUS,c->correlation,c->generation,out);
}
int xw_managed_client_play_mode(struct xw_managed_client *c,uint32_t *native,uint32_t *index){
 if(!native||!index||native==index)return XW_PLAYER_INVALID;
 int rc=control(c,XW_CONTROL_PLAY_MODE,0,0);if(rc)return rc;
 return xw_control_mode_decode(c->remote.reply,c->remote.reply_bytes,c->correlation,c->generation,native,index);
}
int xw_managed_client_sync(struct xw_managed_client *c,struct xw_player_snapshot *out,uint64_t *sequence){
 if(!out||!sequence)return XW_PLAYER_INVALID;int rc=control(c,XW_CONTROL_SNAPSHOT_SYNC,0,0);if(rc)return rc;
 return xw_control_sync_decode(c->remote.reply,c->remote.reply_bytes,c->correlation,out,sequence,&c->response);
}
int xw_managed_client_events(struct xw_managed_client *c,uint64_t after,uint32_t limit,struct xw_service_event *out,uint32_t capacity,uint32_t *count,uint64_t *next){
 if(!out||!count||!next||!limit||limit>XW_EVENT_SLOTS||capacity<limit)return XW_PLAYER_INVALID;
 int rc=control(c,XW_CONTROL_EVENTS,after,limit);if(rc)return rc;
 return xw_control_events_decode(c->remote.reply,c->remote.reply_bytes,c->correlation,after,limit,out,capacity,count,next);
}
int xw_managed_client_end(struct xw_managed_client *c,struct xw_session_snapshot *out){
 if(!out)return XW_PLAYER_INVALID;int rc=control(c,XW_CONTROL_CLOSE,0,0);if(rc)return rc;
 return xw_control_status_decode(c->remote.reply,c->remote.reply_bytes,XW_CONTROL_CLOSE,c->correlation,c->generation,out);
}
