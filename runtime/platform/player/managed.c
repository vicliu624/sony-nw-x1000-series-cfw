#include "managed.h"
#include <string.h>
typedef char command_payload_fits[(16u+2u*XW_MEDIA_ID_BYTES<=XW_REQUEST_BYTES)?1:-1];
static int admit(struct xw_managed_player *,uint32_t);
static int command_id(unsigned char *out,const char *in,int empty){
 unsigned n=0;while(n<XW_MEDIA_ID_BYTES&&in[n]){unsigned c=(unsigned char)in[n];if(c<33||c>126)return XW_PLAYER_INVALID;n++;}
 if(n==XW_MEDIA_ID_BYTES||(!empty&&!n))return XW_PLAYER_INVALID;
 memset(out,0,XW_MEDIA_ID_BYTES);memcpy(out,in,n);return 0;
}
static int observe(void *context,struct xw_player_snapshot *out){return xw_managed_player_snapshot(context,out);}
static int observer_close(void *context){(void)context;return 0;}
static int read_epoch(struct xw_managed_player *p,uint32_t capability,uint64_t *epoch){
 int rc=admit(p,capability);if(rc)return rc;
 return xw_session_admit(p->manager,p->requests.session,capability,epoch)?XW_PLAYER_UNAVAILABLE:0;
}
static int admit(struct xw_managed_player *p,uint32_t capability){
 if(!p||!p->backend)return XW_PLAYER_CLOSED;if(p->busy)return XW_PLAYER_BUSY;
 uint64_t epoch;int rc=xw_session_admit(p->manager,p->requests.session,capability,&epoch);
 return !rc?0:rc==XW_SESSION_BUSY?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;
}
int xw_managed_player_mode_bind(struct xw_managed_player *p,void *context,int (*read)(void *,uint32_t *,uint32_t *)){
 if(!p||!p->backend||!read)return XW_PLAYER_INVALID;
 if(p->busy||p->mode_read)return XW_PLAYER_BUSY;
 p->mode_context=context;p->mode_read=read;return 0;
}
int xw_managed_player_mode_get(struct xw_managed_player *p,uint32_t *raw,uint32_t *index){
 if(!raw||!index||raw==index)return XW_PLAYER_INVALID;
 uint64_t before,after;int rc=read_epoch(p,XW_PLAYER_GRANT_READ,&before);if(rc)return rc;
 if(!p->mode_read)return XW_PLAYER_UNSUPPORTED;
 uint32_t native=UINT32_MAX,menu=UINT32_MAX;p->busy=1;
 rc=p->mode_read(p->mode_context,&native,&menu);p->busy=0;if(rc)return rc;
 rc=read_epoch(p,XW_PLAYER_GRANT_READ,&after);if(rc)return rc;if(before!=after)return XW_PLAYER_UNAVAILABLE;
 if(!((native<=3&&menu==native)||(native==5&&menu==4)))return XW_PLAYER_PROTOCOL;
 *raw=native;*index=menu;return 0;
}
int xw_managed_player_bind(struct xw_managed_player *p,struct xw_session_manager *m,struct xw_session_handle h,struct xw_player *backend){
 if(!p||!m||!backend||!backend->initialized||p->backend)return XW_PLAYER_INVALID;
 int rc=xw_requests_init(&p->requests,m,h);if(rc)return XW_PLAYER_UNAVAILABLE;
 p->manager=m;p->backend=backend;
 if(xw_events_init(&p->events,h.generation))return XW_PLAYER_INVALID;
 struct xw_player_provider provider={XW_PLAYER_API,0,p,observe,0,0,observer_close};
 return xw_player_bind(&p->observer,&provider);
}
int xw_managed_player_snapshot(struct xw_managed_player *p,struct xw_player_snapshot *out){
 if(!out)return XW_PLAYER_INVALID;
 uint64_t before,after;int rc=read_epoch(p,XW_PLAYER_GRANT_READ,&before);if(rc)return rc;
 struct xw_player_snapshot sample;
 p->busy=1;rc=xw_player_snapshot(p->backend,&sample);p->busy=0;if(rc)return rc;
 rc=read_epoch(p,XW_PLAYER_GRANT_READ,&after);if(rc)return rc;if(before!=after)return XW_PLAYER_UNAVAILABLE;
 *out=sample;return 0;
}
int xw_managed_player_poll(struct xw_managed_player *p,struct xw_player_snapshot *out,uint32_t *changes){
 if(!out||!changes)return XW_PLAYER_INVALID;
 if(!p||!p->backend)return XW_PLAYER_CLOSED;
 if(p->busy||p->observer.busy)return XW_PLAYER_BUSY;
 /* The observer's provider checks the grant on every read. Its existing poll
  * implementation invalidates history on failure and preserves outputs. */
 if(p->notification_fault)return XW_PLAYER_IO;
 struct xw_player_snapshot sample;uint32_t changed;
 int rc=xw_player_poll(&p->observer,&sample,&changed);
 uint64_t epoch=1;struct xw_session_snapshot session;
 if(!xw_session_read(p->manager,p->requests.session,&session))epoch=session.epoch;
 if(rc){
  if(!p->unavailable){
   if(xw_events_push(&p->events,epoch,XW_PLAYER_EVENT_UNAVAILABLE,(uint32_t)rc))p->notification_fault=1;
   p->unavailable=1;
  }
  return rc;
 }
 if(changed&&xw_events_push(&p->events,epoch,XW_PLAYER_EVENT_CHANGED,changed)){p->notification_fault=1;return XW_PLAYER_IO;}
 p->unavailable=0;*out=sample;*changes=changed;return 0;
}
int xw_managed_player_refresh(struct xw_managed_player *p){
 struct xw_player_snapshot sample;uint32_t changes;return xw_managed_player_poll(p,&sample,&changes);
}
int xw_managed_player_snapshot_sync(struct xw_managed_player *p,struct xw_player_snapshot *out,uint64_t *sequence){
 if(!out||!sequence)return XW_PLAYER_INVALID;
 struct xw_player_snapshot sample;uint32_t changes;int rc=xw_managed_player_poll(p,&sample,&changes);
 if(rc)return rc;*out=sample;*sequence=p->events.last;return 0;
}
int xw_managed_player_events(struct xw_managed_player *p,uint64_t generation,uint64_t after,struct xw_service_event *events,uint32_t capacity,uint32_t *count,uint64_t *next){
 if(admit(p,XW_PLAYER_GRANT_READ))return XW_EVENTS_RESYNC;
 return xw_events_read(&p->events,generation,after,events,capacity,count,next);
}
int xw_managed_player_browse(struct xw_managed_player *p,const struct xw_media_query *q,struct xw_media_item *items,uint32_t capacity,struct xw_media_page *page){
 if(!q||!items||!page||!capacity||q->limit>capacity)return XW_PLAYER_INVALID;
 uint64_t before,after;int rc=read_epoch(p,XW_PLAYER_GRANT_BROWSE,&before);if(rc)return rc;
 struct xw_media_page staged;
 p->busy=1;rc=xw_media_browse(p->backend,q,p->observer.browse_scratch,capacity<XW_MEDIA_PAGE_MAX?capacity:XW_MEDIA_PAGE_MAX,&staged);p->busy=0;if(rc)return rc;
 rc=read_epoch(p,XW_PLAYER_GRANT_BROWSE,&after);if(rc)return rc;if(before!=after)return XW_PLAYER_UNAVAILABLE;
 memcpy(items,p->observer.browse_scratch,staged.count*sizeof *items);*page=staged;return 0;
}
int xw_managed_player_command(struct xw_managed_player *p,uint64_t id,const struct xw_player_command *c){
 if(!c||!id||c->operation<0||c->operation>=XW_OP_COUNT)return XW_PLAYER_INVALID;
 int rc=admit(p,XW_PLAYER_GRANT_CONTROL);if(rc)return rc;
 /* Canonical explicit scalar encoding; do not compare C padding. Simple
  * controls reject unused IDs/revisions rather than losing their semantics. */
 if(c->operation!=XW_OP_PLAY_ITEM&&(c->item.value[0]||c->container.value[0]||c->expected_revision))return XW_PLAYER_INVALID;
 if(c->operation!=XW_OP_STEP_VOLUME&&c->operation!=XW_OP_SET_VOLUME&&c->value)return XW_PLAYER_INVALID;
 unsigned char payload[16+2*XW_MEDIA_ID_BYTES];uint32_t bytes=8,words[2]={(uint32_t)c->operation,(uint32_t)c->value};
 for(unsigned i=0;i<8;i++)payload[i]=(unsigned char)(words[i/4]>>(8*(i%4)));
 if(c->operation==XW_OP_PLAY_ITEM){
  if(command_id(payload+8,c->item.value,0)||command_id(payload+8+XW_MEDIA_ID_BYTES,c->container.value,1))return XW_PLAYER_INVALID;
  for(unsigned i=0;i<8;i++)payload[8+2*XW_MEDIA_ID_BYTES+i]=(unsigned char)(c->expected_revision>>(8*i));
  bytes=sizeof payload;
 }
 rc=xw_request_submit(&p->requests,p->manager,id,XW_PLAYER_GRANT_CONTROL,payload,bytes);
 if(rc==XW_REQUEST_DUPLICATE){struct xw_request_record r;if(xw_request_read(&p->requests,id,&r))return XW_PLAYER_UNCERTAIN;return r.state==XW_REQUEST_DONE?r.result:XW_PLAYER_BUSY;}
 if(rc)return rc==XW_SESSION_BUSY?XW_PLAYER_BUSY:rc==XW_REQUEST_UNKNOWN?XW_PLAYER_UNCERTAIN:XW_PLAYER_INVALID;
 if(xw_request_start(&p->requests,p->manager,id))return XW_PLAYER_UNAVAILABLE;
 p->busy=1;rc=xw_player_command(p->backend,c);p->busy=0;
 if(xw_request_finish(&p->requests,id,rc))return XW_PLAYER_UNCERTAIN;return rc;
}
static int released(void *context,struct xw_session_handle h,uint32_t reason){
 (void)context;(void)h;(void)reason;return 0; /* No backend resources owned. */
}
int xw_managed_player_close(struct xw_managed_player *p){
 if(!p||!p->backend)return XW_PLAYER_CLOSED;if(p->busy)return XW_PLAYER_BUSY;
 int rc=xw_session_revoke(p->manager,p->requests.session,XW_SESSION_CLIENT_CLOSE);
 if(rc<0)return XW_PLAYER_UNAVAILABLE;
 rc=xw_session_close_step(p->manager,p->requests.session,released,p);
 if(rc)return XW_PLAYER_UNAVAILABLE;
 rc=xw_player_close(&p->observer);if(rc)return rc;p->backend=0;return 0;
}
