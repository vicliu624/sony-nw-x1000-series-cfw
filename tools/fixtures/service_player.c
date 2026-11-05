#include "../../runtime/platform/player/managed.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static unsigned commands,closed;
static int read_error;
static int selection_result=XW_PLAYER_BUSY;
static enum xw_play_state state=XW_PLAY_PLAYING;
static int snapshot(void *c,struct xw_player_snapshot *s){(void)c;if(read_error)return read_error;s->valid=XW_PF_STATE;s->state=state;return 0;}
static int command(void *c,const struct xw_player_command *r){(void)c;commands++;if(r->operation==XW_OP_PLAY_ITEM){assert(!strcmp(r->item.value,"selection:1")&&r->expected_revision==0x1122334455667788ull);return selection_result;}return XW_PLAYER_UNCERTAIN;}
static int close_backend(void *c){(void)c;closed++;return 0;}
int main(void){
 static struct xw_session_manager manager;static struct xw_player backend;static struct xw_managed_player p;
 struct xw_player_provider provider={XW_PLAYER_API,(1u<<XW_OP_NEXT)|(1u<<XW_OP_PLAY_ITEM),0,snapshot,command,0,close_backend};
 struct xw_session_handle h;assert(!xw_sessions_init(&manager,8,7)&&!xw_session_open(&manager,3,3,&h));
 assert(!xw_player_bind(&backend,&provider)&&!xw_managed_player_bind(&p,&manager,h,&backend));
 struct xw_player_command next={0};next.operation=XW_OP_NEXT;
 assert(xw_managed_player_command(&p,1,&next)==XW_PLAYER_UNCERTAIN&&commands==1);
 assert(xw_managed_player_command(&p,1,&next)==XW_PLAYER_UNCERTAIN&&commands==1);
 next.operation=XW_OP_PAUSE;assert(xw_managed_player_command(&p,1,&next)==XW_PLAYER_INVALID&&commands==1);
 struct xw_player_command selection={0};selection.operation=XW_OP_PLAY_ITEM;strcpy(selection.item.value,"selection:1");selection.expected_revision=0x1122334455667788ull;
 assert(xw_managed_player_command(&p,2,&selection)==XW_PLAYER_BUSY&&commands==2);
 selection.item.value[30]='x'; /* Bytes after NUL do not change identity. */
 assert(xw_managed_player_command(&p,2,&selection)==XW_PLAYER_BUSY&&commands==2);
 selection_result=XW_PLAYER_ACCEPTED;
 assert(xw_managed_player_command(&p,3,&selection)==XW_PLAYER_ACCEPTED&&commands==3);
 assert(xw_managed_player_command(&p,3,&selection)==XW_PLAYER_ACCEPTED&&commands==3);
 selection.expected_revision++;assert(xw_managed_player_command(&p,3,&selection)==XW_PLAYER_INVALID&&commands==3);selection.expected_revision--;
 strcpy(selection.container.value,"selection:list");assert(xw_managed_player_command(&p,3,&selection)==XW_PLAYER_INVALID&&commands==3);selection.container.value[0]=0;
 memset(selection.item.value,'x',sizeof selection.item.value);assert(xw_managed_player_command(&p,4,&selection)==XW_PLAYER_INVALID&&commands==3);
 strcpy(selection.item.value,"selection:1");selection_result=XW_PLAYER_UNCERTAIN;
 assert(xw_managed_player_command(&p,4,&selection)==XW_PLAYER_UNCERTAIN&&commands==4);
 assert(xw_managed_player_command(&p,4,&selection)==XW_PLAYER_UNCERTAIN&&commands==4);
 struct xw_player_snapshot observed={0},old;assert(!xw_managed_player_snapshot(&p,&observed)&&observed.state==XW_PLAY_PLAYING);
 static struct xw_managed_player second;struct xw_session_handle h2;
 assert(!xw_session_open(&manager,1,1,&h2)&&!xw_managed_player_bind(&second,&manager,h2,&backend));
 uint32_t changes=0;
 assert(!xw_managed_player_poll(&p,&observed,&changes)&&(changes&XW_PC_AVAILABLE));
 assert(!xw_managed_player_poll(&second,&observed,&changes)&&(changes&XW_PC_AVAILABLE));
 assert(!xw_managed_player_poll(&p,&observed,&changes)&&!changes);
 state=XW_PLAY_PAUSED;
 assert(!xw_managed_player_poll(&p,&observed,&changes)&&(changes&XW_PC_STATE));
 assert(!xw_managed_player_poll(&second,&observed,&changes)&&(changes&XW_PC_STATE));
 old=observed;changes=0x1234;read_error=XW_PLAYER_UNAVAILABLE;
 assert(xw_managed_player_poll(&p,&observed,&changes)==XW_PLAYER_UNAVAILABLE&&changes==0x1234&&!memcmp(&old,&observed,sizeof old));
 read_error=0;assert(!xw_managed_player_poll(&p,&observed,&changes)&&(changes&XW_PC_AVAILABLE));
 assert(!xw_managed_player_poll(&second,&observed,&changes)&&!changes);
 struct xw_service_event events[16];uint32_t count;uint64_t cursor;
 assert(!xw_managed_player_snapshot_sync(&p,&observed,&cursor));
 uint64_t saved_cursor=cursor;
 for(unsigned i=0;i<18;i++){state=i%2?XW_PLAY_PAUSED:XW_PLAY_PLAYING;assert(!xw_managed_player_refresh(&p));}
 assert(xw_managed_player_events(&p,h.generation,saved_cursor,events,16,&count,&cursor)==XW_EVENTS_RESYNC);
 assert(!xw_managed_player_snapshot_sync(&p,&observed,&cursor));
 assert(!xw_managed_player_events(&p,h.generation,cursor,events,16,&count,&saved_cursor)&&!count&&saved_cursor==cursor);
 read_error=XW_PLAYER_UNAVAILABLE;assert(xw_managed_player_refresh(&p)==XW_PLAYER_UNAVAILABLE);
 assert(!xw_managed_player_events(&p,h.generation,cursor,events,16,&count,&saved_cursor)&&count==1&&events[0].kind==XW_PLAYER_EVENT_UNAVAILABLE);
 read_error=0;assert(!xw_managed_player_refresh(&p));
 old=observed;assert(xw_session_revoke(&manager,h,XW_SESSION_USB)==XW_SESSION_PENDING);
 assert(xw_managed_player_snapshot(&p,&observed)==XW_PLAYER_UNAVAILABLE&&!memcmp(&old,&observed,sizeof old));
 assert(!xw_managed_player_close(&p)&&backend.initialized&&!closed);
 assert(!xw_managed_player_poll(&second,&observed,&changes));
 assert(!xw_managed_player_close(&second)&&backend.initialized&&!closed);
 assert(!xw_player_close(&backend)&&closed==1);
 puts("Managed player: grants, one uncertain command, duplicate/conflict refusal, revocation and borrowed backend preservation passed");return 0;
}
