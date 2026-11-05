/* Analysis host source selection wiring; no installed-system modifications. */
#include "host_hook.h"
#include "source_service.h"
extern unsigned long pthread_self(void);
static struct xw_stock_gui *gui;
static struct xw_source_service service;
static struct xw_player_source_provider provider;
void xw_player_host_source_gui(struct xw_stock_gui *value){
 if(value&&value->bound&&value->owner==pthread_self()&&!value->busy&&(!gui||gui==value))gui=value;
}
int xw_player_host_source_attach(struct xw_player_broker *broker){
 if(!broker||!broker->backend||!broker->player.initialized)return XW_PLAYER_CLOSED;
 if(!gui)return XW_PLAYER_UNAVAILABLE;
 if(gui->owner!=pthread_self()||broker->owner!=pthread_self())return XW_PLAYER_BUSY;
 if(broker->source.command)return 0;
 if(broker->backend->provider.commands&(1u<<XW_OP_PLAY_ITEM))return XW_PLAYER_UNSUPPORTED;
 if(!service.bound){int rc=xw_source_service_init(&service,gui,&provider);if(rc)return rc;}
 return xw_player_broker_attach_source(broker,&provider);
}
