#include "player_broker.h"
#include "../../store/deadline.h"
#include <string.h>
extern unsigned long pthread_self(void);
static int revoke_queue(struct xw_player_broker *,uint64_t);
static void revoke_observations(struct xw_player_broker *b,uint64_t now){
 if(b->metadata_ready){struct xw_media_item unused;xw_metadata_async_observe(&b->metadata,0,0,now,&unused);}
 if(b->library_ready)xw_children_async_observe(&b->library,0,0,now,&b->browse_scratch);
 if(b->queue.revoke)revoke_queue(b,now);
}
static int snapshot(void *context,struct xw_player_snapshot *out){
 struct xw_player_broker *b=context;struct xw_player_snapshot value;struct xw_media_item metadata;unsigned long long now=0;
 int clock_valid=!hb_monotonic_millis(&now),timed=b->metadata_ready&&clock_valid;
 if(!clock_valid)revoke_observations(b,0);
 int rc=xw_player_snapshot(b->backend,&value);
 if(rc){if(timed)xw_metadata_async_observe(&b->metadata,0,0,now,&metadata);return rc;}
 if(timed){
  const struct xw_media_id *id=(value.valid&XW_PF_TRACK)&&xw_stock_media_source_ready()?&value.track.id:0;
  int read=xw_metadata_async_observe(&b->metadata,id,value.library_revision,now,&metadata);
  if(!read&&id&&!memcmp(id->value,metadata.id.value,sizeof id->value)){
   memcpy(value.track.title,metadata.title,sizeof value.track.title);memcpy(value.track.artist,metadata.artist,sizeof value.track.artist);memcpy(value.track.album,metadata.album,sizeof value.track.album);value.track.flags=metadata.flags;
   value.valid|=XW_PF_METADATA;
  }
 }
 *out=value;return 0;
}
static int command(void *context,const struct xw_player_command *c){struct xw_player_broker *b=context;return xw_player_command(b->backend,c);}
static int revoke_queue(struct xw_player_broker *b,uint64_t now){
 b->queue_revoke_pending=1;int rc=b->queue.revoke(b->queue.context,now);if(!rc)b->queue_revoke_pending=0;return rc;
}
static int browse(void *context,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 struct xw_player_broker *b=context;int rc=xw_media_browse(b->backend,q,items,XW_MEDIA_PAGE_MAX,page);
 if(rc!=XW_PLAYER_UNSUPPORTED)return rc;
 if(q->view==XW_MEDIA_QUEUE){
  if(!b->queue.browse)return XW_PLAYER_UNSUPPORTED;
  if(q->container.value[0])return XW_PLAYER_UNSUPPORTED;
  unsigned long long now;if(hb_monotonic_millis(&now)){revoke_observations(b,0);return XW_PLAYER_UNAVAILABLE;}
  if(!xw_stock_media_source_ready()){revoke_queue(b,now);return XW_PLAYER_UNAVAILABLE;}
  if(b->queue_revoke_pending){int revoked=revoke_queue(b,now);if(revoked)return revoked;}
  return b->queue.browse(b->queue.context,q,now,items,page);
 }
 if(q->view!=XW_MEDIA_PLAYLIST_TRACKS&&q->container.value[0])return XW_PLAYER_UNSUPPORTED;
 if(!b->library_ready)return XW_PLAYER_UNAVAILABLE;
 unsigned long long now;if(hb_monotonic_millis(&now)){revoke_observations(b,0);return XW_PLAYER_UNAVAILABLE;}
 struct xw_stock_children_page *result=&b->browse_scratch;
 if(!xw_stock_media_source_ready()){xw_children_async_observe(&b->library,0,0,now,result);return XW_PLAYER_UNAVAILABLE;}
 struct xw_player_snapshot state;rc=xw_player_snapshot(b->backend,&state);if(rc)return rc;
 if(q->expected_revision&&q->expected_revision!=state.library_revision)return XW_PLAYER_STALE;
 struct xw_stock_children_query native={0};native.kind=q->view==XW_MEDIA_TRACKS?XW_STOCK_TRACKS:q->view==XW_MEDIA_PLAYLISTS?XW_STOCK_FORMAT3_LISTS:XW_STOCK_FORMAT3_CHILDREN;
 native.offset=q->offset;native.limit=q->limit;if(q->view==XW_MEDIA_PLAYLIST_TRACKS)native.parent=q->container;
 rc=xw_children_async_observe(&b->library,&native,state.library_revision,now,result);if(rc)return rc;
 struct xw_media_page value={state.library_revision,q->offset,result->count,XW_MEDIA_TOTAL_UNKNOWN,q->offset+result->count};
 memcpy(items,result->items,result->count*sizeof *items);*page=value;return 0;
}
static int close_broker(void *context){
 struct xw_player_broker *b=context;
 if(b->queue.close){int rc=b->queue.close(b->queue.context);if(rc)return rc;memset(&b->queue,0,sizeof b->queue);b->queue_revoke_pending=0;}
 if(b->library_ready){int rc=xw_metadata_async_stop(&b->library.worker);if(rc<0)return rc;if(!xw_metadata_async_drained(&b->library.worker))return XW_PLAYER_BUSY;rc=xw_metadata_async_destroy(&b->library.worker);if(rc)return rc;b->library_ready=0;}
 if(b->metadata_ready){int rc=xw_metadata_async_stop(&b->metadata);if(rc<0)return rc;if(!xw_metadata_async_drained(&b->metadata))return XW_PLAYER_BUSY;rc=xw_metadata_async_destroy(&b->metadata);if(rc)return rc;b->metadata_ready=0;}b->backend=0;return 0;
}
int xw_player_broker_bind(struct xw_player_broker *b,struct xw_player *backend){
 if(!b||!backend)return XW_PLAYER_INVALID;if(b->backend||b->player.initialized)return XW_PLAYER_BUSY;if(!backend->initialized)return XW_PLAYER_CLOSED;
 memset(b,0,sizeof *b);b->owner=pthread_self();b->backend=backend;b->metadata_ready=xw_metadata_async_init(&b->metadata)==0;b->library_ready=xw_children_async_init(&b->library)==0;
 struct xw_player_provider provider={XW_PLAYER_API,backend->provider.commands,b,snapshot,command,browse,close_broker};
 int rc=xw_player_bind(&b->player,&provider);if(rc){close_broker(b);}return rc;
}
int xw_player_broker_attach_queue(struct xw_player_broker *b,const struct xw_player_queue_provider *q){
 if(!b||!q||!q->context||!q->browse||!q->revoke||!q->close)return XW_PLAYER_INVALID;
 if(!b->backend||!b->player.initialized)return XW_PLAYER_CLOSED;
 if(b->owner!=pthread_self()||b->player.busy||b->queue.browse)return XW_PLAYER_BUSY;
 b->queue=*q;return 0;
}
void xw_player_broker_tick(struct xw_player_broker *b,unsigned long long now){
 if(b&&!xw_stock_media_source_ready())revoke_observations(b,now);
}
