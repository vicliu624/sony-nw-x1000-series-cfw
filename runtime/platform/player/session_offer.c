#include "session_offer.h"
#include "../services/descriptor.h"
#include <sys/socket.h>
#include <unistd.h>
static int unacquired(void *context,struct xw_session_handle h,uint32_t reason){(void)context;(void)h;(void)reason;return 0;}
int xw_player_session_offer(struct xw_player_session_offer *o,struct xw_session_manager *m,struct xw_player *backend,int delivery,uint32_t requested,uint32_t authorized,uint64_t now){
 if(!o||o->player.backend||o->player.requests.session.serial||o->channel.bound||!backend||!backend->initialized)return XW_PLAYER_INVALID;
 struct xw_session_handle h;int rc=xw_session_open(m,requested,authorized,&h);if(rc)return rc;
 rc=xw_managed_player_bind(&o->player,m,h,backend);if(rc){xw_session_revoke(m,h,XW_SESSION_CLIENT_CLOSE);xw_session_close_step(m,h,unacquired,0);return rc;}
 int pair[2];if(socketpair(AF_UNIX,SOCK_STREAM,0,pair)){xw_managed_player_close(&o->player);return XW_PLAYER_IO;}
 rc=xw_managed_channel_open(&o->channel,&o->player,pair[0],now);
 if(rc){close(pair[0]);close(pair[1]);xw_managed_player_close(&o->player);return rc;}
 struct xw_descriptor_offer offer={h.generation,h.serial,requested};rc=xw_service_descriptor_send(delivery,pair[1],&offer);close(pair[1]);
 if(rc){xw_managed_channel_close(&o->channel);return rc;}return 0;
}
int xw_player_session_offer_tick(struct xw_player_session_offer *o,uint64_t now){
 if(!o)return XW_PLAYER_INVALID;return xw_managed_channel_tick(&o->channel,now);
}
