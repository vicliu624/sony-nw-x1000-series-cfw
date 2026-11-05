/* Adapter policy only: backend and native view operations are modeled. */
#include "../../runtime/platform/player/remote_page_guard.h"
#include "../../runtime/platform/player/player.h"
#include "../../runtime/apps/wireless-remote/native_page_bridge.h"
#include "../../runtime/apps/wireless-remote/native_choice_view.h"
#include <assert.h>
#include <stdio.h>
static unsigned long thread=17;
static int available,requests,end_error,complete,restores;
static struct wr_settings_backend backend;
unsigned long pthread_self(void){return thread;}
struct wr_settings_backend *xw_player_host_remote_page_backend(void){return available?&backend:0;}
int wr_settings_backend_query(struct wr_settings_backend *b,struct wr_settings_view *out){
 if(b->owner!=thread)return XW_PLAYER_BUSY;
 out->phase=b->phase;out->pending=b->pending_enabled!=0;
 out->requested_enabled=b->pending_enabled?b->pending_enabled==2:b->phase==WR_SETTINGS_STARTING;out->error=0;return 0;
}
int wr_settings_backend_request_enabled(struct wr_settings_backend *b,int enabled){
 assert(b->owner==thread&&(enabled==0||enabled==1));requests++;b->pending_enabled=enabled?2:1;return XW_PLAYER_ACCEPTED;
}
int wr_native_choice_view_begin(struct wr_native_choice_view *p,unsigned long owner){
 assert(owner==thread);if(p->held)return XW_PLAYER_BUSY;
 p->owner=thread;p->held=1;p->closing=0;p->epoch++;return 0;
}
int wr_native_choice_view_end(struct wr_native_choice_view *p){
 assert(p->owner==thread&&p->held);if(end_error)return end_error;p->closing=1;return 0;
}
int wr_native_choice_view_observe(struct wr_native_choice_view *p){
 assert(p->owner==thread&&p->held&&p->closing);
 if(!complete)return XW_PLAYER_BUSY;p->held=p->closing=0;restores++;return 0;
}
static uint32_t reply(int rc){return WR_NATIVE_PAGE_STATUS_TAG|((uint32_t)rc&0xffffu);}
int main(void){
 backend.owner=17;backend.phase=WR_SETTINGS_OFF;backend.generation=41;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_OPEN,0)==reply(XW_PLAYER_UNAVAILABLE));
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_ALLOW_WIRELESS,0)==reply(0));
 available=1;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_OPEN,0)==(WR_NATIVE_PAGE_ROW_TAG|1));
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_PREVIEW,0)==reply(0)&&!requests);
 end_error=XW_PLAYER_BUSY;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_CANCEL,0)==reply(XW_PLAYER_BUSY));
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_QUERY,0)==WR_NATIVE_PAGE_ROW_TAG);
 end_error=0;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_APPLY,0)==reply(XW_PLAYER_ACCEPTED)&&requests==1);
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_CANCEL,0)==reply(0)&&backend.pending_enabled==2);
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_OPEN,0)==reply(XW_PLAYER_BUSY)&&!restores);
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_ALLOW_WIRELESS,0)==reply(XW_PLAYER_BUSY));
 complete=1;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_ALLOW_WIRELESS,0)==reply(0)&&restores==1);
 complete=0;
 backend.phase=WR_SETTINGS_STARTING;backend.pending_enabled=0;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_OPEN,0)==WR_NATIVE_PAGE_ROW_TAG);
 thread=18;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_OPEN,0)==reply(XW_PLAYER_BUSY));
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_CANCEL,0)==reply(XW_PLAYER_BUSY));
 xw_player_host_remote_page_tick();assert(restores==1);thread=17;
 backend.generation=42;
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_APPLY,0)==reply(XW_PLAYER_STALE)&&requests==1);
 assert(xw_player_host_remote_page_request(WR_NATIVE_PAGE_CANCEL,0)==reply(0));
 complete=1;xw_player_host_remote_page_tick();assert(restores==2);
 puts("REMOTE_PAGE_ADAPTER_POLICY_PASS");return 0;
}
