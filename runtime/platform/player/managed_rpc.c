#include "managed_rpc.h"
#include <string.h>
int xw_managed_rpc_execute(struct xw_managed_player *p,const unsigned char *frame,size_t bytes,struct xw_rpc_response *out){
 if(!p||!frame||!out)return XW_PLAYER_INVALID;
 struct xw_rpc_request r;int rc=xw_rpc_decode_request(frame,bytes,&r);if(rc)return rc;
 if(!r.serial)return XW_PLAYER_INVALID;
 memset(out,0,sizeof *out);out->kind=r.kind;out->serial=r.serial;
 switch(r.kind){
 case XW_RPC_COMMAND:out->result=xw_managed_player_command(p,r.serial,&r.body.command);break;
 case XW_RPC_SNAPSHOT:out->result=xw_managed_player_snapshot(p,&out->body.snapshot);break;
 case XW_RPC_BROWSE:out->result=xw_managed_player_browse(p,&r.body.query,out->body.browse.items,XW_MEDIA_PAGE_MAX,&out->body.browse.page);break;
 case XW_RPC_HELLO:{
  struct xw_session_snapshot s;
  if(!p->backend||xw_session_read(p->manager,p->requests.session,&s)||s.state!=XW_SESSION_ACTIVE){out->result=XW_PLAYER_UNAVAILABLE;break;}
  if(s.grants&XW_PLAYER_GRANT_CONTROL)out->body.commands=p->backend->provider.commands;
  break;
 }
 default:return XW_PLAYER_PROTOCOL;
 }
 return 0;
}
