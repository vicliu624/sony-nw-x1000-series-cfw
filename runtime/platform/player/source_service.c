#include "source_service.h"
#include "local_identity.h"
#include <string.h>
extern unsigned long pthread_self(void);
#define SOURCE_BOUND 0x58575353u
static int owner(struct xw_source_service *s){
 if(!s||s->bound!=SOURCE_BOUND||!s->intent.check.worker.initialized)return XW_PLAYER_CLOSED;
 return s->intent.check.worker.owner==pthread_self()?0:XW_PLAYER_BUSY;
}
static int command(void *context,const struct xw_player_command *request,uint64_t now){
 struct xw_source_service *s=context;int rc=owner(s);if(rc)return rc;
 if(s->closing)return XW_PLAYER_CLOSED;
 if(!request||request->operation!=XW_OP_PLAY_ITEM)return XW_PLAYER_INVALID;
 if(request->container.value[0])return XW_PLAYER_UNSUPPORTED;
 uint32_t domain,number;struct xw_media_id id;
 if(xw_local_media_id_parse(&request->item,&domain,&number)||!number)return XW_PLAYER_INVALID;
 rc=xw_local_media_id_format(domain,number,&id);if(rc)return rc;
 if(!s->pending||s->revision!=request->expected_revision||memcmp(s->requested.value,id.value,sizeof id.value)){
  if(s->generation==UINT64_MAX)return XW_PLAYER_UNAVAILABLE;
  s->generation++;s->requested=id;s->revision=request->expected_revision;s->pending=1;
 }
 struct xw_stock_source_result receipt;
 rc=xw_source_intent_observe(&s->intent,&s->requested,s->generation,now,&receipt);
 if(s->intent.terminal||s->intent.cancelled||(rc!=XW_PLAYER_BUSY&&rc!=XW_PLAYER_UNAVAILABLE))s->pending=0;
 return rc;
}
static int revoke(void *context,uint64_t now){
 struct xw_source_service *s=context;int rc=owner(s);if(rc)return rc;
 struct xw_stock_source_result ignored;rc=xw_source_intent_observe(&s->intent,0,0,now,&ignored);
 if(!rc)s->pending=0;return rc;
}
static int close_service(void *context){
 struct xw_source_service *s=context;int rc=owner(s);if(rc)return rc;
 rc=xw_metadata_async_stop(&s->intent.check.worker);if(rc<0)return rc;s->closing=1;s->pending=0;
 if(!xw_metadata_async_drained(&s->intent.check.worker))return XW_PLAYER_BUSY;
 rc=xw_metadata_async_destroy(&s->intent.check.worker);if(rc)return rc;
 memset(s,0,sizeof *s);return 0;
}
int xw_source_service_init(struct xw_source_service *s,struct xw_stock_gui *gui,struct xw_player_source_provider *out){
 if(!s||!gui||!out)return XW_PLAYER_INVALID;
 if(s->bound||s->intent.check.worker.initialized)return XW_PLAYER_BUSY;
 memset(s,0,sizeof *s);int rc=xw_source_intent_init(&s->intent,gui);if(rc)return rc;
 s->bound=SOURCE_BOUND;
 struct xw_player_source_provider provider={s,command,revoke,close_service};*out=provider;return 0;
}
