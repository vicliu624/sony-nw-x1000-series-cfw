#include "download_task.h"
#include "tls_platform.h"
#include "download_plan.h"
#include <string.h>
#include <unistd.h>
static void wipe(void *pointer,unsigned bytes){volatile unsigned char *p=pointer;while(bytes--)*p++=0;}
static int close_transport(struct hb_download_task *t){
 int result=0;hb_dns_release(&t->dns);if(hb_connect_release(&t->connection))result=-1;
 if(t->fd>=0){if(close(t->fd))result=-1;t->fd=-1;}
 wipe(&t->client,sizeof t->client);wipe(&t->verifier,sizeof t->verifier);wipe(t->buffer,sizeof t->buffer);
 return result;
}
static int fail(struct hb_download_task *t,int error){
 t->stage_error=error;
 if(error==HB_DNS_DEADLINE||error==HB_CONNECT_DEADLINE||error==HB_HTTPS_DEADLINE)error=HB_NET_DEADLINE;
 if(error==HB_DNS_CLOCK||error==HB_CONNECT_CLOCK||error==HB_HTTPS_CLOCK)error=HB_NET_CLOCK;
 if(error==HB_DNS_CANCELLED||error==HB_CONNECT_CANCELLED||error==HB_DOWNLOAD_CANCELLED)error=HB_NET_CANCELLED;
 t->phase=HB_NET_FAILED;t->error=error;t->tls_error=t->fetch.tls_error;t->ares_status=t->dns.ares_status;
 t->address_count=t->address_index=0;
 if(close_transport(t))t->cleanup_pending=1;
 if(t->file.state==HB_FETCH_READY)t->file.state=HB_FETCH_REVIEW;
 if(t->file.owns){t->file.body.state=HB_DOWNLOAD_FAILED;t->file.body.error=error;}
 if(hb_download_file_discard(&t->file))t->cleanup_pending=1;
 return error;
}
static int budget(struct hb_download_task *t){
 if(t->stop&&*t->stop)return HB_NET_CANCELLED;
 unsigned wait;int result=hb_transfer_deadline_remaining(&t->deadline,&wait);
 return result<0?HB_NET_CLOCK:result?0:HB_NET_DEADLINE;
}
void hb_download_task_init(struct hb_download_task *t){
 if(t){memset(t,0,sizeof *t);t->fd=-1;hb_dns_init(&t->dns);hb_connect_init(&t->connection);hb_download_file_init(&t->file);}
}
int hb_download_task_begin(struct hb_download_task *t,const char *url,const br_x509_trust_anchor *anchors,size_t count,
 const char *cache,const char *key,unsigned bytes,const unsigned char *digest,unsigned long long reserve,unsigned timeout,
 volatile int *stop,const struct ares_options *options,int mask){
 if(!t||t->phase!=HB_NET_EMPTY||!anchors||!count||t->fd>=0||t->dns.channel||t->connection.fd>=0||t->file.state!=HB_FETCH_EMPTY||t->file.owns)return HB_NET_INPUT;
 hb_dns_init(&t->dns);hb_connect_init(&t->connection);memset(&t->fetch,0,sizeof t->fetch);
 t->address_count=t->address_index=0;
 t->stop=stop;t->cleanup_pending=0;t->error=t->stage_error=t->tls_error=t->ares_status=0;
 t->anchors=anchors;t->anchor_count=count;t->options=options;t->option_mask=mask;t->redirects=0;
 if(hb_https_url_parse(url,&t->url))return fail(t,HB_NET_INPUT);
 if(hb_transfer_deadline_init(&t->deadline,timeout))return fail(t,HB_NET_CLOCK);
 int result=budget(t);if(result)return fail(t,result);
 result=hb_download_file_begin(&t->file,cache,key,bytes,digest,reserve,stop);if(result)return fail(t,result);
 unsigned char seed[48];result=hb_tls_seed(seed,stop);if(result)return fail(t,result==HB_TLS_PLATFORM_CANCELLED?HB_NET_CANCELLED:HB_NET_ENTROPY);
 struct hb_tls_time now;if(hb_tls_current_time(&now)){wipe(seed,sizeof seed);return fail(t,HB_NET_TIME);}
 br_ssl_client_init_full(&t->client,&t->verifier,anchors,count);
 br_ssl_engine_set_versions(&t->client.eng,BR_TLS12,BR_TLS12);
 br_ssl_engine_set_buffer(&t->client.eng,t->buffer,sizeof t->buffer,1);
 br_x509_minimal_set_time(&t->verifier,now.days,now.seconds);
 br_ssl_engine_inject_entropy(&t->client.eng,seed,sizeof seed);wipe(seed,sizeof seed);
 if(!br_ssl_client_reset(&t->client,t->url.host,0))return fail(t,HB_NET_TLS_INIT);
 result=budget(t);if(result)return fail(t,result);
 result=hb_dns_begin(&t->dns,t->url.host,t->url.port,&t->deadline,stop,options,mask);
 if(result<0)return fail(t,result);
 t->phase=HB_NET_DNS;return 0;
}
static int transfer_ready(struct hb_download_task *t){
 t->fd=hb_connect_take(&t->connection);if(t->fd<0)return fail(t,HB_NET_IO);
 int result=hb_https_fetch_init(&t->fetch,&t->client.eng,t->fd,&t->file,&t->deadline,t->url.host,t->url.port,t->url.path);
 if(result)return fail(t,result);
 t->phase=HB_NET_TRANSFER;return 0;
}
static int next_address(struct hb_download_task *t,int result){
 if(result!=HB_CONNECT_IO||t->address_index+1>=t->address_count)return fail(t,result);
 t->address_index++;hb_connect_init(&t->connection);return 0;
}
int hb_download_task_step(struct hb_download_task *t,unsigned cap){
 if(!t)return HB_NET_INPUT;
 if(t->phase==HB_NET_FAILED)return t->error;
 if(t->phase==HB_NET_DONE)return 1;
 if(t->phase==HB_NET_EMPTY)return HB_NET_INPUT;
 if(cap>1000)return fail(t,HB_NET_INPUT);
 int result=budget(t);if(result)return fail(t,result);
 if(t->phase==HB_NET_DNS){
  result=hb_dns_step(&t->dns,cap);if(result<0)return fail(t,result);if(!result)return 0;
  t->address_count=t->dns.count;if(!t->address_count)return fail(t,HB_DNS_FORMAT);
  memcpy(t->addresses,t->dns.addresses,t->address_count*sizeof t->addresses[0]);hb_dns_release(&t->dns);
  t->address_index=0;t->phase=HB_NET_CONNECT;return 0;
 }
 if(t->phase==HB_NET_CONNECT){
  if(t->connection.state==HB_CONNECT_EMPTY)result=hb_connect_begin(&t->connection,AF_INET,(const struct sockaddr *)(t->addresses+t->address_index),sizeof t->addresses[0],&t->deadline,t->stop);
  else result=hb_connect_step(&t->connection,cap);
  if(result<0)return next_address(t,result);
  if(result==1)return transfer_ready(t);
  return 0;
 }
 result=hb_https_fetch_step(&t->fetch,cap);if(result<0)return fail(t,result);if(!result)return 0;
 if(result==2){
  struct hb_https_url next;
  if(++t->redirects>5||t->file.body.received||hb_https_url_parse(t->fetch.response.location,&next))return fail(t,HB_NET_INPUT);
  if(close_transport(t))return fail(t,HB_NET_IO);
  t->url=next;t->address_count=t->address_index=0;memset(&t->fetch,0,sizeof t->fetch);
  unsigned char seed[48];struct hb_tls_time clock;
  if(hb_tls_seed(seed,t->stop))return fail(t,HB_NET_ENTROPY);
  if(hb_tls_current_time(&clock)){wipe(seed,sizeof seed);return fail(t,HB_NET_TIME);}
  br_ssl_client_init_full(&t->client,&t->verifier,t->anchors,t->anchor_count);
  br_ssl_engine_set_versions(&t->client.eng,BR_TLS12,BR_TLS12);
  br_ssl_engine_set_buffer(&t->client.eng,t->buffer,sizeof t->buffer,1);
  br_x509_minimal_set_time(&t->verifier,clock.days,clock.seconds);
  br_ssl_engine_inject_entropy(&t->client.eng,seed,sizeof seed);wipe(seed,sizeof seed);
  if(!br_ssl_client_reset(&t->client,t->url.host,0))return fail(t,HB_NET_TLS_INIT);
  hb_dns_init(&t->dns);hb_connect_init(&t->connection);
  result=hb_dns_begin(&t->dns,t->url.host,t->url.port,&t->deadline,t->stop,t->options,t->option_mask);
  if(result<0)return fail(t,result);
  t->phase=HB_NET_DNS;return 0;
 }
 result=budget(t);if(result)return fail(t,result);
 if(close_transport(t)){t->cleanup_pending=1;return fail(t,HB_NET_IO);}
 result=budget(t);if(result)return fail(t,result);
 t->phase=HB_NET_DONE;return 1;
}
int hb_download_task_discard(struct hb_download_task *t){
 if(!t)return HB_NET_INPUT;
 int previous=t->phase==HB_NET_FAILED?t->error:HB_NET_CANCELLED;t->phase=HB_NET_FAILED;t->error=previous;
 int result=close_transport(t);int file=hb_download_file_discard(&t->file);
 if(result||file){t->cleanup_pending=1;return file?file:HB_NET_IO;}
 t->cleanup_pending=0;t->address_count=t->address_index=0;t->phase=HB_NET_EMPTY;return 0;
}
int hb_download_task_begin_file(struct hb_download_task *t,const struct hb_package_download_plan *plan,unsigned index,
 const br_x509_trust_anchor *anchors,size_t count,const char *cache,unsigned long long reserve,unsigned timeout,
 volatile int *stop,const struct ares_options *options,int mask){
 struct hb_package_download_file file;
 if(hb_package_download_plan_file(plan,index,&file))return HB_NET_INPUT;
 return hb_download_task_begin(t,file.url,anchors,count,cache,file.cache_key,file.bytes,file.digest,reserve,timeout,stop,options,mask);
}

int hb_download_task_cancel(struct hb_download_task *t){
 if(!t||t->phase==HB_NET_EMPTY)return HB_NET_INPUT;
 if(t->phase==HB_NET_FAILED)return t->error;
 return fail(t,HB_NET_CANCELLED);
}
