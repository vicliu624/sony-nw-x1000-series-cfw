#include "xnow_endpoint.h"
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
int xnow_endpoint_init(struct xnow_endpoint *e,struct xnow_full *t,unsigned channel,unsigned limit,void *context,int (*random)(void *,uint8_t[4])){
 if(!e||!t||!random||channel<1||channel>14||limit>XNOW_ENCRYPTED_PEER_LIMIT||t->fault||t->stopping||t->inflight)return XNOW_ARGUMENT;
 memset(e,0,sizeof(*e));e->transport=t;e->channel=channel;e->random_context=context;e->random=random;return xnow_peer_init(&e->peers,limit);
}
int xnow_endpoint_add(struct xnow_endpoint *e,const struct xnow_peer *p){if(!e||!e->transport)return XNOW_ARGUMENT;if(e->active||e->stopping)return XNOW_PENDING;return xnow_peer_add(&e->peers,p);}
int xnow_endpoint_modify(struct xnow_endpoint *e,const struct xnow_peer *p){if(!e||!e->transport)return XNOW_ARGUMENT;if(e->active||e->stopping)return XNOW_PENDING;int r=xnow_peer_modify(&e->peers,p);if(!r&&e->crypto.forget)e->crypto.forget(e->crypto.context,p->address);return r;}
int xnow_endpoint_delete(struct xnow_endpoint *e,const uint8_t a[6]){if(!e||!e->transport||!a)return XNOW_ARGUMENT;if(e->active||e->stopping)return XNOW_PENDING;uint8_t address[6];memcpy(address,a,6);int r=xnow_peer_delete(&e->peers,address);if(!r&&e->crypto.forget)e->crypto.forget(e->crypto.context,address);return r;}
static int target(struct xnow_endpoint *e,const uint8_t a[6],size_t n,unsigned slot){
 struct xnow_peer p;int r=xnow_peer_validate_send(&e->peers,a,e->channel,n,&p);
 if(r)return r==XNOW_PEER_CHANNEL?XNOW_ENDPOINT_CHANNEL:r==XNOW_PEER_LENGTH?XNOW_ENDPOINT_LENGTH:XNOW_ENDPOINT_PEER;
 if(p.encrypt&&(!e->crypto.prepare||!e->crypto.send||!e->crypto.receive||e->crypto.prepare(e->crypto.context,&p))){wipe(&p,sizeof(p));return XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;}
 e->encrypted[slot]=p.encrypt;
 memcpy(e->targets[slot],p.address,6);e->versions[slot]=p.version;wipe(&p,sizeof(p));return 0;
}
int xnow_endpoint_send(struct xnow_endpoint *e,const uint8_t destination[6],const void *data,size_t n){
 if(!e||!e->transport||(!data&&n)||n>XNOW_ESPNOW_V2_MAX)return XNOW_ARGUMENT;
 if(e->transport->fault)return XNOW_UNCERTAIN;
 if(e->active||e->stopping)return XNOW_PENDING;
 unsigned count=0;int r=0;
 if(destination){r=target(e,destination,n,0);count=1;}
 else for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)if(e->peers.used[i]){r=target(e,e->peers.peers[i].address,n,count);if(r)break;count++;}
 if(r||!count){wipe(e->targets,sizeof(e->targets));wipe(e->versions,sizeof(e->versions));return r?r:XNOW_ENDPOINT_PEER;}
 if(n)memcpy(e->payload,data,n);
 e->bytes=n;e->count=count;e->index=0;e->waiting=0;e->active=1;return 0;
}
static void advance(struct xnow_endpoint *e){e->waiting=0;if(++e->index==e->count){e->active=0;wipe(e->payload,sizeof(e->payload));e->bytes=0;}}
int xnow_endpoint_poll(struct xnow_endpoint *e,struct xnow_endpoint_result *out){
 if(!e||!e->transport||!out)return XNOW_ARGUMENT;
 if(e->transport->fault)return XNOW_UNCERTAIN;
 if(e->stopping)return XNOW_PENDING;
 if(!e->active)return XNOW_AGAIN;
 struct xnow_endpoint_result result;memset(&result,0,sizeof(result));memcpy(result.destination,e->targets[e->index],6);
 if(e->waiting){struct xnow_full_result done;int r=xnow_full_tx_result(e->transport,&done);if(r)return r;
  result.stock_status=done.stock_status;result.raw_fields=done.raw_fields;advance(e);*out=result;return 0;}
 uint8_t random[4];int r=e->random(e->random_context,random);
 if(r){wipe(random,sizeof(random));return XNOW_IO;}
 if(e->encrypted[e->index])r=e->crypto.send(e->crypto.context,e->transport,e->targets[e->index],e->versions[e->index],random,e->payload,e->bytes);
 else r=xnow_full_send(e->transport,e->targets[e->index],e->versions[e->index],random,e->payload,e->bytes);
 wipe(random,sizeof(random));
 if(r==XNOW_PENDING)return r;
 if(r==XNOW_UNCERTAIN)return r;
 if(r){result.result=r;advance(e);*out=result;return 0;}
 e->waiting=1;return XNOW_PENDING;
}
int xnow_endpoint_receive(struct xnow_endpoint *e,void *out,size_t n,struct xnow_full_received *info){
 if(!e||!e->transport||!info||(!out&&n))return XNOW_ARGUMENT;
 if(e->stopping)return XNOW_PENDING;
 if(e->crypto.receive)return e->crypto.receive(e->crypto.context,e->transport,out,n,info);
 uint8_t data[XNOW_ESPNOW_V2_MAX];struct xnow_full_received found;
 int r=xnow_full_receive(e->transport,data,n<sizeof(data)?n:sizeof(data),&found);
 if(r==XNOW_FULL_PROTECTED){wipe(data,sizeof(data));int discarded=xnow_full_discard(e->transport);return discarded?discarded:XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;}
 if(r){wipe(data,sizeof(data));return r;}
 struct xnow_peer peer;
 if(!xnow_peer_get(&e->peers,found.source,&peer)){
  unsigned encrypted=peer.encrypt;wipe(&peer,sizeof(peer));
  if(encrypted&&!(found.flags&XNOW_RX_BROADCAST)){wipe(data,sizeof(data));return XNOW_ENDPOINT_CRYPTO_UNAVAILABLE;}
 }
 if(found.info.payload_bytes)memcpy(out,data,found.info.payload_bytes);
 *info=found;wipe(data,sizeof(data));return 0;
}
int xnow_endpoint_stop_step(struct xnow_endpoint *e){
 if(!e||!e->transport)return XNOW_ARGUMENT;
 e->stopping=1;int r=xnow_full_stop_step(e->transport);
 if(r)return r;
 if(e->crypto.clear)e->crypto.clear(e->crypto.context);
 xnow_peer_clear(&e->peers);wipe(e->payload,sizeof(e->payload));wipe(e->targets,sizeof(e->targets));wipe(e->versions,sizeof(e->versions));wipe(e->encrypted,sizeof(e->encrypted));e->active=0;e->waiting=0;e->count=0;e->bytes=0;return 0;
}
