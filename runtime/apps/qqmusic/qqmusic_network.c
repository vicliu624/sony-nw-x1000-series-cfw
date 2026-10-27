#include "qqmusic_network.h"
#include <string.h>
#include <unistd.h>
#include "../../store/https_url.h"
static void media_abort(void *context){struct qq_network *n=context;if(n->media_sink_active){n->media_sink_active=0;n->media_sink.abort(n->media_sink.opaque);}}
static int media_write(void *context,const unsigned char *p,size_t bytes){struct qq_network *n=context;return n->media_sink_active?n->media_sink.write(n->media_sink.opaque,p,bytes):-1;}
static int media_finish(void *context,uint64_t bytes,const unsigned char digest[32]){struct qq_network *n=context;int rc;if(!n->media_sink_active)return -1;rc=n->media_sink.finish(n->media_sink.opaque,bytes,digest);if(!rc)n->media_sink_active=0;return rc;}
static int copy(char *out,size_t cap,const char *input) {
 size_t i;if(!input)return -1;for(i=0;i<cap;i++){out[i]=input[i];if(!input[i])return 0;}return -1;
}
void qq_network_cancel(struct qq_network *n) {
 if(!n)return;
 n->stopped=1;media_abort(n);qq_tls_cancel(&n->transaction);hb_dns_release(&n->dns);hb_connect_release(&n->connection);
 if(n->fd>=0){if(close(n->fd))n->error=-1;n->fd=-1;}
 hb_connect_init(&n->connection);
 qq_secret_clear(&n->request,sizeof(n->request));qq_secret_clear(&n->client,sizeof(n->client));
 qq_secret_clear(&n->verifier,sizeof(n->verifier));qq_secret_clear(n->tls_buffer,sizeof(n->tls_buffer));
 qq_secret_clear(n->body,sizeof(n->body));qq_secret_clear(n->host,sizeof(n->host));qq_secret_clear(n->method,sizeof(n->method));
 n->cookies=0;n->ticket=0;n->phase=QQ_NET_EMPTY;n->deadline.valid=0;
 qq_secret_clear(n->media_url,sizeof(n->media_url));memset(&n->media_sink,0,sizeof(n->media_sink));n->media=n->media_sink_active=0;n->media_maximum=0;
}
static void clock_date(struct qq_connection_diagnostic *d,const struct hb_tls_time *clock){
 static const unsigned months[]={31,28,31,30,31,30,31,31,30,31,30,31};unsigned days,year=1970,month=0,length,leap;
 if(clock->unix_seconds>2147483647ULL)return;
 days=(unsigned)(clock->unix_seconds/86400u);
 for(;;){leap=year%4==0&&(year%100!=0||year%400==0);length=365+leap;if(days<length)break;days-=length;year++;}
 for(;;){length=months[month]+(month==1&&leap);if(days<length)break;days-=length;month++;}
 d->clock_year=year;d->clock_month=month+1;d->clock_day=days+1;
 d->clock_hour=(unsigned)(clock->unix_seconds%86400/3600);d->clock_minute=(unsigned)(clock->unix_seconds%3600/60);
}
static int fail(struct qq_network *n,int error) {
 struct qq_connection_diagnostic d={0};int tls=br_ssl_engine_last_error(&n->client.eng);
 d.step=(error<=HB_DNS_INPUT&&error>=HB_DNS_IO)||n->phase==QQ_NET_DNS?QQ_STEP_DNS:n->phase==QQ_NET_CONNECT?QQ_STEP_TCP:n->phase==QQ_NET_TLS?QQ_STEP_TLS:QQ_STEP_LOCAL;
 d.error=error;d.dns=n->dns.ares_status;d.tls=tls;d.http=n->transaction.response.head.status;
 if(d.step==QQ_STEP_TLS&&!tls&&(d.http||error==-6))d.step=QQ_STEP_HTTP;
 if(error==-4||tls==BR_ERR_X509_EXPIRED){d.step=QQ_STEP_CLOCK;clock_date(&d,&n->clock);}
 qq_network_cancel(n);n->diagnostic=d;n->error=error;n->tls_error=tls;n->phase=QQ_NET_FAILED;return -1;
}
int qq_network_current_time(struct qq_network *n,struct hb_tls_time *out){
 struct hb_tls_time current;
 if(!n||!out||!n->config.time)return -1;
 memset(&current,0,sizeof(current));
 if(n->config.time(&current)){memset(&n->clock,0,sizeof(n->clock));n->clock.unix_seconds=~0ULL;return fail(n,-4);}
 n->clock=current;
 /* Contemporary QQ endpoints cannot be used with a factory-reset-era RTC.
  * This rejects clearly stale dates, not a claim to know today's exact date. */
 if(current.unix_seconds<1609459200ULL||current.unix_seconds>2147483647ULL)return fail(n,-4);
 *out=current;return 0;
}
static void diagnostic(void *context,struct qq_connection_diagnostic *out){struct qq_network *n=context;*out=n->diagnostic;}
static int prepare(void *context,struct qq_runtime_material *out) {struct qq_network *n=context;return n->material(n->application,out);}
static int stock(void *context) {struct qq_network *n=context;return n->stock?n->stock(n->application):-1;}
static void cancel(void *context){qq_network_cancel(context);}
static int start(void *context,const struct qq_request *request,struct qq_cookie_jar *cookies,uint64_t ticket) {
 struct qq_network *n=context;size_t bytes;int rc;
 if(n->phase!=QQ_NET_EMPTY||!request||!cookies||!ticket)return -1;
 n->stopped=0;n->error=0;n->tls_error=0;n->address=0;n->ticket=ticket;n->cookies=cookies;
 memset(&n->diagnostic,0,sizeof(n->diagnostic));
 if(copy(n->host,sizeof(n->host),request->host)||copy(n->method,sizeof(n->method),request->method))return fail(n,-2);
 n->request=*request;n->request.host=n->host;n->request.method=n->method;
 if(hb_transfer_deadline_init(&n->deadline,n->config.timeout_ms))return fail(n,-3);
 if(qq_network_current_time(n,&n->clock))return -1;
 /* Validate origin/path/header scope before even issuing a DNS packet. */
 rc=qq_http_request_wire(&n->request,cookies,n->clock.unix_seconds,n->transaction.wire,sizeof(n->transaction.wire),&bytes);
 qq_secret_clear(n->transaction.wire,sizeof(n->transaction.wire));if(rc)return fail(n,-5);
 rc=hb_dns_begin(&n->dns,n->host,n->config.port,&n->deadline,&n->stopped,n->config.dns_options,n->config.dns_mask);
 if(rc<0)return fail(n,rc);
 n->phase=QQ_NET_DNS;return 0;
}
static int connect_next(struct qq_network *n) {
 int rc;
 while(n->address<n->dns.count) {
  hb_connect_release(&n->connection);hb_connect_init(&n->connection);
  rc=hb_connect_begin(&n->connection,AF_INET,(const struct sockaddr *)&n->dns.addresses[n->address],sizeof(n->dns.addresses[0]),&n->deadline,&n->stopped);
  if(rc>=0){n->phase=QQ_NET_CONNECT;return 0;}
  if(rc!=HB_CONNECT_IO)return fail(n,rc);
  n->address++;
 }
 return fail(n,HB_CONNECT_IO);
}
static int begin_tls(struct qq_network *n) {
 unsigned char seed[48];struct hb_tls_time current;unsigned long long previous=n->clock.unix_seconds;int rc;
 n->fd=hb_connect_take(&n->connection);if(n->fd<0)return fail(n,-6);
 if(qq_network_current_time(n,&current))return -1;
 if(current.unix_seconds<previous)return fail(n,-4);
 n->clock=current;
 memset(seed,0,sizeof(seed));rc=n->config.seed(seed,&n->stopped);
 if(rc){qq_secret_clear(seed,sizeof(seed));return fail(n,-7);}
 br_ssl_client_init_full(&n->client,&n->verifier,n->config.anchors,n->config.anchor_count);
 br_ssl_engine_set_versions(&n->client.eng,BR_TLS12,BR_TLS12);
 br_ssl_engine_set_buffer(&n->client.eng,n->tls_buffer,sizeof(n->tls_buffer),1);
 br_x509_minimal_set_time(&n->verifier,current.days,current.seconds);
 br_ssl_engine_inject_entropy(&n->client.eng,seed,sizeof(seed));qq_secret_clear(seed,sizeof(seed));
 if(!br_ssl_client_reset(&n->client,n->host,0))return fail(n,-8);
 if(n->media){
  struct qq_resource resource;struct qq_response_sink sink={n,media_write,media_finish,media_abort};memset(&resource,0,sizeof(resource));memcpy(resource.url,n->media_url,sizeof(resource.url));
  rc=qq_tls_begin_stream(&n->transaction,&n->client.eng,n->fd,&n->deadline,&n->stopped,&resource,n->media_maximum,sink);
  qq_secret_clear(&resource,sizeof(resource));qq_secret_clear(n->media_url,sizeof(n->media_url));
 }else rc=qq_tls_begin(&n->transaction,&n->client.eng,n->fd,&n->deadline,&n->stopped,&n->request,n->cookies,current.unix_seconds,n->body,sizeof(n->body));
 qq_secret_clear(&n->request,sizeof(n->request));if(rc)return fail(n,-9);
 n->phase=QQ_NET_TLS;return 0;
}
static int poll(void *context,struct qq_response **response) {
 struct qq_network *n=context;int rc;
 if(!response)return -1;
 *response=0;
 if(n->phase==QQ_NET_DNS) {
  rc=hb_dns_step(&n->dns,n->config.poll_ms);if(rc<0)return fail(n,rc);if(!rc)return 0;
  return connect_next(n);
 }
 if(n->phase==QQ_NET_CONNECT) {
  rc=n->connection.state==HB_CONNECT_READY?1:hb_connect_step(&n->connection,n->config.poll_ms);
  if(rc==HB_CONNECT_IO){n->address++;return connect_next(n);}
  if(rc<0)return fail(n,rc);
  return rc?begin_tls(n):0;
 }
 if(n->phase==QQ_NET_TLS) {
  rc=qq_tls_step(&n->transaction,n->config.poll_ms);if(rc<0)return fail(n,n->transaction.error);
  if(!rc)return 0;
  n->phase=QQ_NET_DONE;
 }
 if(n->phase==QQ_NET_DONE){
  const struct qq_response *r=&n->transaction.response;
  /* Only fresh, fully TLS-verified bootstrap responses. Cached artwork/CDN
   * Date values must not be mistaken for a device-clock failure. */
  if(!n->media&&r->phase==QQ_RX_DONE&&r->head.has_date&&
     ((r->anonymous==1&&!strcmp(n->host,"api.tencentmusic.com"))||(r->anonymous==2&&!strcmp(n->host,"u.y.qq.com")))){
   int64_t skew=(int64_t)n->clock.unix_seconds-(int64_t)r->head.server_date;
   if(skew>300||skew< -300){
    struct qq_connection_diagnostic d={0};d.step=QQ_STEP_CLOCK;d.error=-4;d.http=r->head.status;clock_date(&d,&n->clock);
    d.clock_skew_seconds=(int)skew;d.server_hour=(unsigned)(r->head.server_date%86400/3600);d.server_minute=(unsigned)(r->head.server_date%3600/60);
    qq_network_cancel(n);n->diagnostic=d;n->error=-4;n->phase=QQ_NET_FAILED;return -1;
   }
  }
  *response=&n->transaction.response;return 1;
 }
 return -1;
}
int qq_network_init(struct qq_network *n,const struct qq_network_config *config,void *application,
 int (*material)(void *,struct qq_runtime_material *),int (*handoff)(void *)) {
 if(!n||!config||!config->anchors||!config->anchor_count||config->anchor_count>128||!material||
    !config->timeout_ms||config->timeout_ms>60000||config->poll_ms>20||config->port>65535)return -1;
 memset(n,0,sizeof(*n));n->fd=-1;hb_dns_init(&n->dns);hb_connect_init(&n->connection);
 n->config=*config;if(!n->config.port)n->config.port=443;
 if(!n->config.seed)n->config.seed=hb_tls_seed;
 if(!n->config.time)n->config.time=hb_tls_current_time;
 n->application=application;n->material=material;n->stock=handoff;
 n->operations.context=n;n->operations.prepare=prepare;n->operations.start=start;n->operations.poll=poll;
 n->operations.cancel=cancel;n->operations.return_stock=stock;n->operations.diagnostic=diagnostic;return 0;
}
const struct qq_runtime_ops *qq_network_operations(struct qq_network *n) {return n?&n->operations:0;}
int qq_network_media_begin(struct qq_network *n,const struct qq_resource *resource,size_t maximum,unsigned timeout,struct qq_response_sink sink){
 struct hb_https_url url;int rc;
 if(!n||n->phase!=QQ_NET_EMPTY||n->operations.context!=n||!n->config.time||!n->config.seed||!resource||!memchr(resource->url,0,sizeof(resource->url))||!maximum||maximum>268435456||timeout<1000||timeout>900000||!sink.write||!sink.finish||!sink.abort)return -1;
 memset(&url,0,sizeof(url));if(qq_resource_url_parse(resource->url,&url)){qq_secret_clear(&url,sizeof(url));return -1;}
 n->media=1;n->media_sink_active=1;n->media_sink=sink;n->media_maximum=maximum;n->stopped=0;n->error=n->tls_error=0;n->address=0;
 memcpy(n->media_url,resource->url,strlen(resource->url)+1);copy(n->host,sizeof(n->host),url.host);qq_secret_clear(&url,sizeof(url));
 if(hb_transfer_deadline_init(&n->deadline,timeout))return fail(n,-3);
 if(qq_network_current_time(n,&n->clock))return -1;
 rc=hb_dns_begin(&n->dns,n->host,n->config.port,&n->deadline,&n->stopped,n->config.dns_options,n->config.dns_mask);
 if(rc<0)return fail(n,rc);
 n->phase=QQ_NET_DNS;return 0;
}
int qq_network_media_step(struct qq_network *n){struct qq_response *response=0;if(!n||!n->media)return -1;return poll(n,&response);}
