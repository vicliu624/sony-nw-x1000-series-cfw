#include "qqmusic_program.h"
#include "qqmusic_identity.h"
#include "qqmusic_qimei.h"
#include <stdlib.h>
#include <string.h>
struct program {struct qq_identity identity;struct qq_network network;struct qq_cookie_jar bootstrap_cookies;const struct qq_program_config *config;unsigned pending_qimei,pending_platform,deferred_request,request_active;struct qq_runtime_ops operations;struct qq_request platform_request;struct qq_cookie_jar *platform_cookies;uint64_t platform_ticket;struct qq_connection_diagnostic diagnostic;int endpoint;};
static void capture(struct program *p,int step,int error,const struct qq_response *response){
 if(step){memset(&p->diagnostic,0,sizeof(p->diagnostic));p->diagnostic.step=step;p->diagnostic.error=error;}
 else {p->diagnostic=p->network.diagnostic;if(!p->diagnostic.step){p->diagnostic.step=QQ_STEP_LOCAL;p->diagnostic.error=error;}}
 p->diagnostic.endpoint=p->endpoint;
 if(response)p->diagnostic.http=response->head.status;
}
static void diagnostic(void *context,struct qq_connection_diagnostic *out){struct program *p=context;*out=p->diagnostic;}
static int material(void *context,struct qq_runtime_material *out){
 struct program *p=context;const struct qq_runtime_ops *ops=qq_network_operations(&p->network);
 struct qq_request request;struct qq_response *response=0;struct hb_tls_time clock;int rc;
 qq_secret_clear(out,sizeof(*out));
 if(!p->config->stop||*p->config->stop)return -1;
 if(qq_network_current_time(&p->network,&clock)){capture(p,0,-4,0);return -1;}
 if(p->identity.session_bound)return qq_identity_prepare(&p->identity,out);
 if(p->config->ensure_network){
  rc=p->config->ensure_network(p->config->platform_context);p->pending_platform=rc==1;
  if(rc){out->network_stage=1;if(rc<0)capture(p,QQ_STEP_WIFI,rc,0);return rc==1?1:-1;}
 }
 out->network_stage=2;
 if(p->network.phase==QQ_NET_EMPTY){
  p->endpoint=p->identity.qimei_bound?2:1;memset(&p->diagnostic,0,sizeof(p->diagnostic));
  /* An earlier preparation may have been cancelled by the UI. No old response
   * survives network_cancel; request a fresh anonymous session on retry. */
  p->identity.session_pending=0;p->pending_qimei=0;qq_cookie_clear(&p->bootstrap_cookies);
  if(!p->identity.qimei_bound){
   size_t bytes;
   if(!p->config->qimei_payload){capture(p,QQ_STEP_LOCAL,-1,0);return -1;}
   for(bytes=0;bytes<=3072&&p->config->qimei_payload[bytes];bytes++){}
   if(bytes>3072){capture(p,QQ_STEP_LOCAL,-4,0);return -1;}
   rc=qq_qimei_request(&request,p->config->qimei_payload,bytes,clock.unix_seconds,p->config->stop,p->identity.seed);p->pending_qimei=1;
  }else rc=qq_identity_session_request(&p->identity,&request);
  if(rc)capture(p,QQ_STEP_LOCAL,rc,0);
  else {rc=ops->start(ops->context,&request,&p->bootstrap_cookies,1);if(rc)capture(p,0,rc,0);}
  qq_secret_clear(&request,sizeof(request));
  if(rc){qq_network_cancel(&p->network);p->identity.session_pending=0;return -1;}
  return 1;
 }
 rc=ops->poll(ops->context,&response);if(!rc)return 1;
 if(rc<0)capture(p,0,rc,0);
 if(rc==1&&p->pending_qimei){
  struct qq_qimei ids;rc=qq_qimei_accept(response,&ids);if(!rc)rc=qq_identity_bind_qimei(&p->identity,ids.q36);qq_secret_clear(&ids,sizeof(ids));
 }else if(rc==1)rc=qq_identity_session_accept(&p->identity,response);else rc=-1;
 if(rc&&response)capture(p,response->head.status==200?QQ_STEP_REPLY:QQ_STEP_HTTP,rc,response);
 qq_network_cancel(&p->network);qq_cookie_clear(&p->bootstrap_cookies);p->identity.session_pending=0;
 if(rc)return -1;
 if(p->pending_qimei){p->pending_qimei=0;return 1;}
 return qq_identity_prepare(&p->identity,out);
}
static int handoff(void *context){struct program *p=context;return p->config->handoff?p->config->handoff(p->config->handoff_context):-1;}
static int set_utc_offset(void *context,int minutes){
 struct program *p=context;
 if(!p->config->set_utc_offset||p->request_active||p->deferred_request||p->pending_platform||p->identity.session_pending||p->identity.session_bound||p->network.phase!=QQ_NET_EMPTY)return -1;
 return p->config->set_utc_offset(minutes);
}
static void cancel(void *context);
static int start(void *context,const struct qq_request *r,struct qq_cookie_jar *jar,uint64_t ticket){
 struct program *p=context;const struct qq_runtime_ops *ops=qq_network_operations(&p->network);int rc=0;
 if(p->request_active||p->deferred_request||!p->config->stop||*p->config->stop)return -1;
 p->endpoint=3;memset(&p->diagnostic,0,sizeof(p->diagnostic));
 if(p->config->ensure_network)rc=p->config->ensure_network(p->config->platform_context);
 p->pending_platform=rc==1;
 if(*p->config->stop){cancel(p);return -1;}
 if(rc==1){p->platform_request=*r;p->platform_cookies=jar;p->platform_ticket=ticket;p->deferred_request=p->request_active=1;return 0;}
 if(rc){capture(p,QQ_STEP_WIFI,rc,0);return -1;}
 rc=ops->start(ops->context,r,jar,ticket);if(rc)capture(p,0,rc,0);else p->request_active=1;return rc;
}
static int poll_network(void *context,struct qq_response **response){
 struct program *p=context;const struct qq_runtime_ops *ops=qq_network_operations(&p->network);int rc;
 *response=0;
 if(!p->request_active)return 0;
 if(!p->config->stop||*p->config->stop){cancel(p);return -1;}
 if(p->deferred_request){
  rc=p->config->ensure_network(p->config->platform_context);
  if(*p->config->stop){cancel(p);return -1;}
  if(rc==1)return 0;
  p->pending_platform=0;p->deferred_request=0;
  if(rc)capture(p,QQ_STEP_WIFI,rc,0);
  else {rc=ops->start(ops->context,&p->platform_request,p->platform_cookies,p->platform_ticket);if(rc)capture(p,0,rc,0);}
  qq_secret_clear(&p->platform_request,sizeof(p->platform_request));p->platform_cookies=0;p->platform_ticket=0;
  if(rc){p->request_active=0;return -1;}
 }
 rc=ops->poll(ops->context,response);if(rc<0)capture(p,0,rc,0);return rc;
}
static void cancel(void *context){struct program *p=context;unsigned pending=p->pending_platform;p->request_active=p->pending_platform=p->deferred_request=0;qq_network_cancel(&p->network);if(pending&&p->config->cancel_network)p->config->cancel_network(p->config->platform_context);qq_secret_clear(&p->platform_request,sizeof(p->platform_request));p->platform_cookies=0;p->platform_ticket=0;}
int qq_program_run_bound(const struct qq_program_config *config,qq_program_entry run,void *context){
 struct program *p;struct qq_entry_config entry;int network_ready=0,rc=-1;
 if(!config||!run||!config->volume||!config->resources||!config->comm||!config->guid||!config->stop||*config->stop)return -1;
 p=calloc(1,sizeof(*p));if(!p)return -1;p->config=config;
 if(qq_identity_init(&p->identity,config->comm,config->guid,config->stop,0))goto done;
 if(qq_network_init(&p->network,&config->network,p,material,config->handoff?handoff:0))goto done;
 network_ready=1;entry.volume=config->volume;entry.resource_directory=config->resources;
 p->operations.context=p;p->operations.prepare=material;p->operations.start=start;p->operations.poll=poll_network;p->operations.cancel=cancel;p->operations.return_stock=config->handoff?handoff:0;
 p->operations.diagnostic=diagnostic;
 p->operations.set_utc_offset=config->set_utc_offset?set_utc_offset:0;
 entry.operations=&p->operations;entry.stop=config->stop;
 rc=run(&entry,context);
done:if(network_ready)cancel(p);if(config->release_network)config->release_network(config->platform_context);qq_identity_clear(&p->identity);qq_secret_clear(p,sizeof(*p));free(p);return rc;
}
static int entry_default(const struct qq_entry_config *entry,void *unused){(void)unused;return qq_entry_run(entry);}
int qq_program_run(const struct qq_program_config *config){return qq_program_run_bound(config,entry_default,0);}
