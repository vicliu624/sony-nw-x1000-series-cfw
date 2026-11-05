#include "native_page_bridge.h"
#include "../../platform/player/player.h"
extern unsigned long pthread_self(void);
static uint32_t status(int rc){return WR_NATIVE_PAGE_STATUS_TAG|((uint32_t)rc&0xffffu);}
static int owner(struct wr_native_page_bridge *p){return p&&p->backend&&p->owner==pthread_self();}
int wr_native_page_bridge_bind(struct wr_native_page_bridge *p,struct wr_settings_backend *b){
 if(!p||p->backend||!b)return XW_PLAYER_INVALID;
 struct wr_settings_view view;int rc=wr_settings_backend_query(b,&view);if(rc)return rc;
 p->backend=b;p->owner=pthread_self();p->generation=0;p->open=0;p->preview=0;
 p->view_context=0;p->view_begin=0;p->view_end=0;return 0;
}
int wr_native_page_bridge_attach_view(struct wr_native_page_bridge *p,void *context,int (*begin)(void *),int (*end)(void *)){
 if(!owner(p))return XW_PLAYER_BUSY;
 if(!context||!begin||!end)return XW_PLAYER_INVALID;
 if(p->open||p->view_begin||p->view_end)return XW_PLAYER_BUSY;
 p->view_context=context;p->view_begin=begin;p->view_end=end;return 0;
}
int wr_native_page_bridge_unbind(struct wr_native_page_bridge *p){
 if(!owner(p))return XW_PLAYER_BUSY;
 if(p->open)return XW_PLAYER_BUSY;
 p->backend=0;p->owner=0;p->generation=0;p->preview=0;
 p->view_context=0;p->view_begin=0;p->view_end=0;return 0;
}
uint32_t wr_native_page_bridge_request(struct wr_native_page_bridge *p,uint32_t operation,uint32_t row){
 if(!owner(p))return status(XW_PLAYER_BUSY);
 /* Cancel only discards local preview, even after backend retirement/fault.
  * It never cancels a committed backend request or resurrects a generation. */
 if(operation==WR_NATIVE_PAGE_CANCEL){
  if(p->open){int rc=p->view_end?p->view_end(p->view_context):XW_PLAYER_UNAVAILABLE;if(rc)return status(rc);}
  p->open=0;p->generation=0;p->preview=0;return status(0);
 }
 if(operation<WR_NATIVE_PAGE_OPEN||operation>WR_NATIVE_PAGE_APPLY)return status(XW_PLAYER_INVALID);
 if(operation==WR_NATIVE_PAGE_OPEN&&p->open)return status(XW_PLAYER_BUSY);
 if(operation!=WR_NATIVE_PAGE_OPEN&&(!p->open||!p->generation))return status(XW_PLAYER_CLOSED);
 struct wr_settings_view view;int rc=wr_settings_backend_query(p->backend,&view);if(rc)return status(rc);
 if(operation==WR_NATIVE_PAGE_OPEN){
  if(!p->view_begin||!p->view_end)return status(XW_PLAYER_UNAVAILABLE);
  if(view.requested_enabled<0)return status(XW_PLAYER_UNCERTAIN);
  uint64_t generation=p->backend->generation;if(!generation)return status(XW_PLAYER_UNAVAILABLE);
  rc=p->view_begin(p->view_context);if(rc)return status(rc);
  p->generation=generation;
  p->preview=view.requested_enabled?0:1;p->open=1;
  return WR_NATIVE_PAGE_ROW_TAG|p->preview;
 }
 if(p->generation!=p->backend->generation)return status(XW_PLAYER_STALE);
 if(operation==WR_NATIVE_PAGE_QUERY)return WR_NATIVE_PAGE_ROW_TAG|p->preview;
 if(operation==WR_NATIVE_PAGE_PREVIEW){
  if(row>1)return status(XW_PLAYER_INVALID);
  p->preview=row;return status(0);
 }
 return status(wr_settings_backend_request_enabled(p->backend,p->preview==0));
}
