#include "../../runtime/platform/player/managed_rpc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned controls,reads;
static struct xw_session_manager *revoke_manager;
static struct xw_session_handle revoke_handle;
static int state(void *c,struct xw_player_snapshot *s){(void)c;reads++;s->valid=XW_PF_STATE;s->state=XW_PLAY_PLAYING;return 0;}
static int control(void *c,const struct xw_player_command *r){(void)c;(void)r;controls++;return XW_PLAYER_ACCEPTED;}
static int close_backend(void *c){(void)c;return 0;}
static int browse(void *c,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 (void)c;memset(items,0,sizeof *items);strcpy(items->id.value,"fixture:1");strcpy(items->title,"Track");items->flags=XW_MEDIA_TITLE_PRESENT;
 page->offset=q->offset;page->count=1;page->next_offset=q->offset+1;page->total=page->next_offset;
 if(revoke_manager)assert(xw_session_revoke(revoke_manager,revoke_handle,XW_SESSION_USB)==XW_SESSION_PENDING);
 return 0;
}
int main(void){
 static struct xw_session_manager m;static struct xw_player backend;static struct xw_managed_player p;
 static struct xw_rpc_response response,decoded;static unsigned char frame[XW_RPC_PACKET_MAX];size_t bytes;
 struct xw_session_handle h;struct xw_player_provider provider={XW_PLAYER_API,1u<<XW_OP_NEXT,0,state,control,browse,close_backend};
 assert(!xw_sessions_init(&m,7,7)&&!xw_session_open(&m,7,7,&h)&&!xw_player_bind(&backend,&provider)&&!xw_managed_player_bind(&p,&m,h,&backend));
 struct xw_rpc_request r={0};r.kind=XW_RPC_COMMAND;r.serial=1;r.body.command.operation=XW_OP_NEXT;
 assert(!xw_rpc_encode_request(&r,frame,sizeof frame,&bytes));
 assert(!xw_managed_rpc_execute(&p,frame,bytes,&response)&&response.result==XW_PLAYER_ACCEPTED&&controls==1);
 assert(!xw_managed_rpc_execute(&p,frame,bytes,&response)&&response.result==XW_PLAYER_ACCEPTED&&controls==1);
 r.kind=XW_RPC_BROWSE;r.serial=2;memset(&r.body,0,sizeof r.body);r.body.query.limit=1;
 assert(!xw_rpc_encode_request(&r,frame,sizeof frame,&bytes)&&!xw_managed_rpc_execute(&p,frame,bytes,&response));
 assert(!response.result&&response.body.browse.page.count==1);
 assert(!xw_rpc_encode_response(&response,frame,sizeof frame,&bytes)&&!xw_rpc_decode_response(frame,bytes,&decoded)&&!strcmp(decoded.body.browse.items[0].title,"Track"));
 struct xw_media_item item,prior;struct xw_media_page page,previous;
 memset(&item,0x5a,sizeof item);prior=item;memset(&page,0x5a,sizeof page);previous=page;
 revoke_manager=&m;revoke_handle=h;
 assert(xw_managed_player_browse(&p,&r.body.query,&item,1,&page)==XW_PLAYER_UNAVAILABLE);
 assert(!memcmp(&item,&prior,sizeof item)&&!memcmp(&page,&previous,sizeof page));
 assert(xw_session_revoke(&m,h,XW_SESSION_USB)==XW_SESSION_PENDING);
 r.kind=XW_RPC_SNAPSHOT;r.serial=3;assert(!xw_rpc_encode_request(&r,frame,sizeof frame,&bytes)&&!xw_managed_rpc_execute(&p,frame,bytes,&response)&&response.result==XW_PLAYER_UNAVAILABLE&&!reads);
 unsigned before=controls;assert(xw_managed_rpc_execute(&p,frame,3,&response)<0&&controls==before);
 puts("Managed dispatch: exact framing, command dedup, media response and revoked read refusal passed");return 0;
}
