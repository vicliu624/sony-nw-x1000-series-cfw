#include "qqmusic_preview_binding.h"
#include "qqmusic_preview_session.h"
#include "../../native/linux_process.h"
#include "../../store/deadline.h"
#include <string.h>
static int source_child(void *context,const struct qq_preview_worker_job *worker){
 struct qq_preview_binding *b=context;int rc;
 if(qq_import_binding_detach_child(b->imports))return -1;
 rc=qq_preview_source_job_run(&b->source,worker);qq_secret_clear(&b->request,sizeof(b->request));return rc;
}
static int begin(void *context,const struct qq_song *song,const struct qq_resource_intent *intent,const struct qq_resource *resource,const struct qq_export_plan *layout,uint64_t now,uint64_t expires){
 struct qq_preview_binding *b=context;const struct qq_job_config *c=&b->imports->policy;
 if(!b->initialized||b->state||b->client.active||c->exclusive(c->policy_context)||now>=expires||b->imports->worker.pid>0)return -1;
 b->request.song=*song;b->request.intent=*intent;b->request.resource=*resource;b->request.layout=*layout;b->request.now_ms=now;b->request.expires_ms=expires;
 memset(&b->source,0,sizeof(b->source));memset(&b->receipt,0,sizeof(b->receipt));b->source.config=c;b->source.request=&b->request;
 if(qq_preview_receipt_bind(&b->source,&b->receipt)){qq_secret_clear(&b->request,sizeof(b->request));return -1;}
 b->failed=0;b->state=1;b->network_waiting=0;return 0;
}
static void stop(void *context){
 struct qq_preview_binding *b=context;const struct qq_job_config *c=&b->imports->policy;
 if(b->network_waiting&&c->cancel_network)c->cancel_network(c->network_context);
 b->network_waiting=0;
 if(b->state==1){b->state=0;qq_secret_clear(&b->request,sizeof(b->request));}
 else if(b->state==2)(void)qq_preview_client_stop(&b->client);
}
static int poll(void *context,uint64_t now,struct qq_runtime_preview_progress *progress){
 struct qq_preview_binding *b=context;const struct qq_job_config *c=&b->imports->policy;int rc;
 memset(progress,0,sizeof(*progress));progress->failed=b->failed;progress->phase=QQ_UI_PREVIEW_DONE;
 if(!b->state)return 1;
 if(b->state==1){
  progress->phase=QQ_UI_PREVIEW_PREPARING;
  if(*b->client.stop||now>=b->request.expires_ms||c->exclusive(c->policy_context)){b->failed=1;stop(b);progress->failed=1;return 1;}
  if(c->prepare_network){
   rc=c->prepare_network(c->network_context);b->network_waiting=rc==1;
   if(rc==1)return 0;
   if(rc){b->failed=1;stop(b);progress->failed=1;return 1;}
  }
  if(qq_preview_client_begin(&b->client,30000,source_child,b)){b->failed=1;stop(b);progress->failed=1;return 1;}
  b->state=2;
  /* Only the source child's COW snapshot retains the authorization now. */
  qq_secret_clear(&b->request,sizeof(b->request));
 }
 rc=qq_preview_client_poll(&b->client,now);progress->failed=b->failed||b->client.failed;
 progress->seconds=(unsigned)(b->client.frames/44100u);
 if(rc<0){progress->phase=QQ_UI_PREVIEW_REVIEW;return -1;}
 if(rc==1){b->state=0;progress->phase=QQ_UI_PREVIEW_DONE;return 1;}
 switch(b->client.phase){
 case QQ_PREVIEW_IDLE:case QQ_PREVIEW_ACQUIRING:progress->phase=QQ_UI_PREVIEW_PREPARING;break;
 case QQ_PREVIEW_LEASED:progress->phase=QQ_UI_PREVIEW_DOWNLOADING;break;
 case QQ_PREVIEW_CONFIGURING:case QQ_PREVIEW_READY:progress->phase=QQ_UI_PREVIEW_STARTING;break;
 case QQ_PREVIEW_PLAYING:progress->phase=QQ_UI_PREVIEW_PLAYING;break;
 case QQ_PREVIEW_STOPPING:progress->phase=QQ_UI_PREVIEW_STOPPING;break;
 default:progress->phase=QQ_UI_PREVIEW_RESTORING;break;
 }return 0;
}
static int close_binding(void *context){
 struct qq_preview_binding *b=context;struct qq_runtime_preview_progress p;unsigned i;unsigned long long now;int result=0;
 stop(b);
 for(i=0;i<750&&b->state;i++){
  if(hb_monotonic_millis(&now)){result=-1;now=b->client.last_ms;}
  if(poll(b,now,&p)==1)break;
  hb_linux_wait_tick();
 }
 if(b->state){
  result=-1;
  if(!b->client.reaped){(void)hb_linux_kill(b->client.worker);for(i=0;i<50&&!b->client.reaped;i++){(void)qq_preview_client_poll(&b->client,b->client.last_ms);hb_linux_wait_tick();}}
 }
 return result;
}
int qq_preview_binding_attach(struct qq_preview_binding *b,struct qq_import_binding *imports,const struct qq_preview_client_channels *channels,volatile int *stop_token){
 if(!b||!imports||!imports->attached||!imports->runtime||!stop_token)return -1;
 memset(b,0,sizeof(*b));b->imports=imports;
 if(qq_preview_client_init(&b->client,channels,stop_token))return -1;
 b->operations.context=b;b->operations.begin=begin;b->operations.poll=poll;b->operations.stop=stop;b->operations.close=close_binding;b->initialized=1;
 return qq_runtime_bind_preview(imports->runtime,&b->operations);
}
void qq_preview_binding_destroy(struct qq_preview_binding *b){if(!b)return;if(b->initialized)(void)close_binding(b);qq_secret_clear(b,sizeof(*b));}
