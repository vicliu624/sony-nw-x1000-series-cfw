#include "../../runtime/apps/qqmusic/qqmusic_network.c"
#include <assert.h>
#include <stdlib.h>
static int unused(void *p,struct qq_runtime_material *out){(void)p;(void)out;assert(0);return -1;}
static int old_time(struct hb_tls_time *out){out->unix_seconds=1199881535ULL;out->days=719528u+(unsigned)(out->unix_seconds/86400u);out->seconds=(unsigned)(out->unix_seconds%86400u);return 0;}
static int unreadable_time(struct hb_tls_time *out){(void)out;return -1;}
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
int main(void){
 struct qq_network *n=calloc(1,sizeof(*n));struct qq_network_config config;struct qq_connection_diagnostic d,after;br_x509_trust_anchor anchor;
 assert(n);memset(&config,0,sizeof(config));memset(&anchor,0,sizeof(anchor));config.anchors=&anchor;config.anchor_count=1;config.timeout_ms=1000;
 assert(!qq_network_init(n,&config,0,unused,0));n->phase=QQ_NET_DNS;n->dns.ares_status=ARES_ETIMEOUT;assert(fail(n,HB_DNS_LOOKUP)<0);n->operations.diagnostic(n,&d);assert(d.step==QQ_STEP_DNS&&d.error==HB_DNS_LOOKUP&&d.dns==ARES_ETIMEOUT&&!d.tls);qq_network_cancel(n);n->operations.diagnostic(n,&after);assert(!memcmp(&d,&after,sizeof(d)));
 assert(!qq_network_init(n,&config,0,unused,0));n->phase=QQ_NET_TLS;n->client.eng.err=BR_ERR_X509_NOT_TRUSTED;assert(fail(n,-9)<0);n->operations.diagnostic(n,&d);assert(d.step==QQ_STEP_TLS&&d.tls==BR_ERR_X509_NOT_TRUSTED&&!br_ssl_engine_last_error(&n->client.eng));
 assert(!qq_network_init(n,&config,0,unused,0));n->phase=QQ_NET_TLS;n->transaction.response.head.status=503;assert(fail(n,-6)<0);n->operations.diagnostic(n,&d);assert(d.step==QQ_STEP_HTTP&&d.http==503&&!d.tls);qq_network_cancel(n);
 config.time=old_time;assert(!qq_network_init(n,&config,0,unused,0));
 {struct qq_request request;struct qq_cookie_jar jar;memset(&request,0,sizeof(request));memset(&jar,0,sizeof(jar));request.host="graph.qq.com";request.method="GET";assert(n->operations.start(n,&request,&jar,1)<0);}
 n->operations.diagnostic(n,&d);assert(d.step==QQ_STEP_CLOCK&&d.clock_year==2008&&d.clock_month==1&&d.clock_day==9&&n->fd==-1);
 qq_network_cancel(n);n->operations.diagnostic(n,&after);assert(!memcmp(&d,&after,sizeof(d)));
 config.time=unreadable_time;assert(!qq_network_init(n,&config,0,unused,0));
 {struct hb_tls_time t;assert(qq_network_current_time(n,&t)<0);}
 assert(n->diagnostic.step==QQ_STEP_CLOCK&&!n->diagnostic.clock_year);
 assert(!qq_network_init(n,&config,0,unused,0));n->clock.unix_seconds=1793100000ULL;n->phase=QQ_NET_TLS;n->client.eng.err=BR_ERR_X509_EXPIRED;assert(fail(n,-9)<0);assert(n->diagnostic.step==QQ_STEP_CLOCK&&n->diagnostic.tls==BR_ERR_X509_EXPIRED&&n->diagnostic.clock_year==2026);
 {
  const char body[]="{\"code\":-30000,\"data\":null}";char header[256];struct qq_response *response=0;int bytes;
  config.time=0;assert(!qq_network_init(n,&config,0,unused,0));n->clock.unix_seconds=1793139969ULL;strcpy(n->host,"api.tencentmusic.com");
  bytes=sony_snprintf(header,sizeof(header),"HTTP/1.1 200 OK\r\nDate: Tue, 27 Oct 2026 14:26:09 GMT\r\nContent-Length: %u\r\n\r\n",(unsigned)(sizeof(body)-1));assert(bytes>0&&(size_t)bytes<sizeof(header));
  assert(!qq_response_init_qimei(&n->transaction.response,n->body,sizeof(n->body)));
  assert(!qq_response_push(&n->transaction.response,(const unsigned char *)header,(size_t)bytes));
  assert(qq_response_push(&n->transaction.response,(const unsigned char *)body,sizeof(body)-1)==1);
  assert(!qq_response_finish(&n->transaction.response));n->phase=QQ_NET_DONE;
  /* Same failure pattern as the device: complete HTTP200 from bootstrap,
   * signed using a device clock eight hours ahead. No actual TLS in fixture. */
  assert(n->operations.poll(n,&response)<0&&n->diagnostic.step==QQ_STEP_CLOCK&&!response);
  assert(n->diagnostic.clock_skew_seconds==28800&&n->diagnostic.clock_hour==22&&n->diagnostic.server_hour==14&&n->diagnostic.http==200);
  /* Cached artwork Date is not a fresh server-clock assertion. */
  assert(!qq_network_init(n,&config,0,unused,0));n->clock.unix_seconds=1793139969ULL;strcpy(n->host,"y.gtimg.cn");
  assert(!qq_response_init_cover(&n->transaction.response,"/music/photo_new/T002R500x500M000SYNTHETIC.jpg",n->body,sizeof(n->body)));
  assert(!qq_response_push(&n->transaction.response,(const unsigned char *)header,(size_t)bytes));
  assert(qq_response_push(&n->transaction.response,(const unsigned char *)body,sizeof(body)-1)==1);assert(!qq_response_finish(&n->transaction.response));n->phase=QQ_NET_DONE;
  assert(n->operations.poll(n,&response)==1&&response==&n->transaction.response&&n->diagnostic.step!=QQ_STEP_CLOCK);qq_network_cancel(n);
 }
 free(n);return 0;
}
