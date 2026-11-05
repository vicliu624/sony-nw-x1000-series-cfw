/* Hidden native-page adapter. Caller/image/GUI ownership are qualified by
 * host_hook before request; view ports independently qualify their operations.
 * No public SDK binding, radio-mode selection or process startup on OPEN. */
#include "remote_page_guard.h"
#include "player.h"
#include "../../apps/wireless-remote/native_page_bridge.h"
#include "../../apps/wireless-remote/native_choice_view.h"
extern unsigned long pthread_self(void);
static struct wr_native_page_bridge page;
static struct wr_native_choice_view view;
static uint32_t status(int rc){return WR_NATIVE_PAGE_STATUS_TAG|((uint32_t)rc&0xffffu);}
static int begin_view(void *context){
 return wr_native_choice_view_begin(context,pthread_self());
}
static int end_view(void *context){
 struct wr_native_choice_view *p=context;
 return p->held&&p->closing?0:wr_native_choice_view_end(p);
}
static int bind_backend(void){
 struct wr_settings_backend *backend=xw_player_host_remote_page_backend();
 if(!backend)return XW_PLAYER_UNAVAILABLE;
 if(page.backend)return page.backend==backend&&page.owner==pthread_self()?0:XW_PLAYER_BUSY;
 int rc=wr_native_page_bridge_bind(&page,backend);if(rc)return rc;
 rc=wr_native_page_bridge_attach_view(&page,&view,begin_view,end_view);
 if(rc)(void)wr_native_page_bridge_unbind(&page);
 return rc;
}
void xw_player_host_remote_page_tick(void){
 if(!page.backend||page.owner!=pthread_self()||!view.held||!view.closing)return;
 (void)wr_native_choice_view_observe(&view);
}
uint32_t xw_player_host_remote_page_request(uint32_t operation,uint32_t row){
 if(operation==WR_NATIVE_PAGE_ALLOW_WIRELESS){
  if(row)return status(XW_PLAYER_UNSUPPORTED);
  xw_player_host_remote_page_tick();
  return status(view.held?XW_PLAYER_BUSY:0);
 }
 if(operation==WR_NATIVE_PAGE_CANCEL&&!page.backend)return status(0);
 if(operation==WR_NATIVE_PAGE_OPEN){
  xw_player_host_remote_page_tick();
  int rc=bind_backend();if(rc)return status(rc);
 }
 if(!page.backend)return status(XW_PLAYER_CLOSED);
 return wr_native_page_bridge_request(&page,operation,row);
}
