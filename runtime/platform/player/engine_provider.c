#include "engine_provider.h"
extern unsigned long pthread_self(void);
static int available(struct xw_engine_provider *p){
 if(!p||!p->bound||!p->original)return XW_PLAYER_CLOSED;
 if(p->busy||p->owner!=pthread_self())return XW_PLAYER_BUSY;
 return p->original->initialized?0:XW_PLAYER_UNAVAILABLE;
}
static int snapshot(void *context,struct xw_player_snapshot *out){
 struct xw_engine_provider *p=context;int rc=available(p);if(rc)return rc;
 p->busy=1;rc=xw_player_snapshot(p->original,out);p->busy=0;return rc;
}
static int command(void *context,const struct xw_player_command *c){
 struct xw_engine_provider *p=context;int rc=available(p);if(rc)return rc;
 if(c->operation>=XW_OP_PLAY&&c->operation<=XW_OP_PREVIOUS&&
    (c->value||c->item.value[0]||c->container.value[0]||c->expected_revision))return XW_PLAYER_INVALID;
 p->busy=1;
 if(c->operation>=XW_OP_PLAY&&c->operation<=XW_OP_PREVIOUS)
  rc=xw_stock_engine_control_command(&p->engine,c->operation);
 else rc=xw_player_command(p->original,c);
 p->busy=0;return rc;
}
static int browse(void *context,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 struct xw_engine_provider *p=context;int rc=available(p);if(rc)return rc;
 p->busy=1;rc=xw_media_browse(p->original,q,items,q->limit,page);p->busy=0;return rc;
}
static int close_provider(void *context){
 struct xw_engine_provider *p=context;
 if(!p||!p->bound)return XW_PLAYER_CLOSED;
 if(p->busy||p->owner!=pthread_self())return XW_PLAYER_BUSY;
 int rc=xw_stock_engine_control_unbind(&p->engine);if(rc)return rc;
 p->original=0;p->bound=0;p->owner=0;return 0;
}
int xw_engine_player_bind(struct xw_player *player,struct xw_engine_provider *p,struct xw_player *original){
 if(!player||!p||!original||player==original||!original->initialized)return XW_PLAYER_INVALID;
 if(player->initialized||p->bound||p->engine.bound)return XW_PLAYER_BUSY;
 int rc=xw_stock_engine_control_bind(&p->engine);if(rc)return rc;
 p->original=original;p->owner=pthread_self();p->busy=0;p->bound=1;
 uint32_t transport=(1u<<XW_OP_PLAY)|(1u<<XW_OP_PAUSE)|(1u<<XW_OP_NEXT)|(1u<<XW_OP_PREVIOUS);
 struct xw_player_provider provider={XW_PLAYER_API,original->provider.commands|transport,p,snapshot,command,original->provider.browse?browse:0,close_provider};
 rc=xw_player_bind(player,&provider);if(rc)close_provider(p);return rc;
}
