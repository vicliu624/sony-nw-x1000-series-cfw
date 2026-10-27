#include "qqmusic_tls.h"
#include "../../store/https_url.h"
#include <string.h>
void qq_tls_cancel(struct qq_tls_transaction *t) {
 if(!t) return;
 qq_response_cancel(&t->response);qq_secret_clear(t->wire,sizeof(t->wire));
 t->wire_bytes=t->sent=0;t->phase=QQ_TLS_FAILED;t->error=-1;
}
static int fail(struct qq_tls_transaction *t,int error) {
 qq_tls_cancel(t);t->error=error;return -1;
}
static int budget(struct qq_tls_transaction *t) {
 unsigned wait;
 if(t->stop&&*t->stop) return -2;
 return hb_transfer_deadline_remaining(t->deadline,&wait)==1?0:-3;
}
int qq_tls_begin(struct qq_tls_transaction *t,br_ssl_engine_context *engine,int fd,
 struct hb_transfer_deadline *deadline,volatile int *stop,const struct qq_request *r,
 struct qq_cookie_jar *jar,uint64_t now,unsigned char *body,size_t capacity) {
 char path[2049];size_t i;
 if(!t) return -1;
 memset(t,0,sizeof(*t));t->phase=QQ_TLS_FAILED;
 if(!engine||fd<0||!deadline||!deadline->valid||!r||!r->host||!jar||!body||!capacity) return -1;
 t->engine=engine;t->fd=fd;t->deadline=deadline;t->stop=stop;
 if(!br_ssl_engine_get_server_name(engine)||strcmp(br_ssl_engine_get_server_name(engine),r->host)) return fail(t,-4);
 if(qq_http_request_wire(r,jar,now,t->wire,sizeof(t->wire),&t->wire_bytes)) return fail(t,-4);
 memset(path,0,sizeof(path));
 for(i=0;i<sizeof(path)-1&&r->path[i]&&r->path[i]!='?';i++) path[i]=r->path[i];
 if(r->qimei?qq_response_init_qimei(&t->response,body,capacity):r->anonymous_session?qq_response_init_session(&t->response,body,capacity):r->album_cover?qq_response_init_cover(&t->response,path,body,capacity):
    !strcmp(r->host,"u.y.qq.com")&&!strcmp(r->path,"/cgi-bin/musicu.fcg")&&!strcmp(r->method,"POST")&&r->json_body?
    qq_response_init_cgi(&t->response,jar,now,body,capacity):qq_response_init(&t->response,jar,r->host,path,now,body,capacity)) return fail(t,-4);
 t->phase=QQ_TLS_SENDING;
 if(budget(t)) return fail(t,-3);
 return 0;
}
int qq_tls_begin_stream(struct qq_tls_transaction *t,br_ssl_engine_context *engine,int fd,
 struct hb_transfer_deadline *deadline,volatile int *stop,const struct qq_resource *resource,
 size_t maximum,struct qq_response_sink sink) {
 struct hb_https_url url;size_t used=0,i;const char *parts[5];
 if(!t) return -1;
 memset(t,0,sizeof(*t));t->phase=QQ_TLS_FAILED;
 if(!engine||fd<0||!deadline||!deadline->valid||!resource||qq_resource_url_parse(resource->url,&url)) return -1;
 t->engine=engine;t->fd=fd;t->deadline=deadline;t->stop=stop;
 if(!br_ssl_engine_get_server_name(engine)||strcmp(br_ssl_engine_get_server_name(engine),url.host)) return fail(t,-4);
 if(qq_response_init_stream(&t->response,maximum,sink)) return fail(t,-4);
 parts[0]="GET ";parts[1]=url.path;parts[2]=" HTTP/1.1\r\nHost: ";parts[3]=url.host;
 parts[4]="\r\nAccept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n";
 for(i=0;i<5;i++) {size_t n=strlen(parts[i]);if(n>=sizeof(t->wire)-used) return fail(t,-4);memcpy(t->wire+used,parts[i],n);used+=n;}
 t->wire_bytes=used;t->wire[used]=0;t->phase=QQ_TLS_SENDING;
 qq_secret_clear(&url,sizeof(url));
 if(budget(t)) return fail(t,-3);
 return 0;
}
int qq_tls_step(struct qq_tls_transaction *t,unsigned cap) {
 unsigned state;size_t n;int rc;
 if(!t||t->phase==QQ_TLS_FAILED) return -1;
 if(t->phase==QQ_TLS_DONE) return 1;
 if(cap>1000) return fail(t,-4);
 rc=budget(t);if(rc) return fail(t,rc);
 if(br_ssl_engine_last_error(t->engine)) return fail(t,-5);
 state=br_ssl_engine_current_state(t->engine);
 if(state&BR_SSL_CLOSED) {
  if(t->phase!=QQ_TLS_RECEIVING||qq_response_finish(&t->response)) return fail(t,-6);
  qq_secret_clear(t->wire,sizeof(t->wire));t->phase=QQ_TLS_DONE;return 1;
 }
 if(t->phase==QQ_TLS_SENDING&&(state&BR_SSL_SENDAPP)) {
  unsigned char *out=br_ssl_engine_sendapp_buf(t->engine,&n);
  size_t left=t->wire_bytes-t->sent;
  if(!out||!n||!left) return fail(t,-5);
  if(n>left) n=left;
  memcpy(out,t->wire+t->sent,n);br_ssl_engine_sendapp_ack(t->engine,n);t->sent+=n;
  if(t->sent==t->wire_bytes) {
   br_ssl_engine_flush(t->engine,0);t->phase=QQ_TLS_RECEIVING;
   qq_secret_clear(t->wire,sizeof(t->wire));
  }
  rc=budget(t);return rc?fail(t,rc):0;
 }
 if(state&BR_SSL_RECVAPP) {
  unsigned char *input;
  if(t->phase!=QQ_TLS_RECEIVING) return fail(t,-6);
  input=br_ssl_engine_recvapp_buf(t->engine,&n);
  if(!input||!n) return fail(t,-5);
  if(n>4096) n=4096;
  rc=qq_response_push(&t->response,input,n);br_ssl_engine_recvapp_ack(t->engine,n);
  if(rc<0) return fail(t,rc<=-100?rc:-6);
  rc=budget(t);return rc?fail(t,rc):0;
 }
 rc=hb_tls_socket_deadline_step(t->engine,t->fd,t->deadline,cap,t->stop);
 if(rc==HB_TLS_SOCKET_EOF&&t->phase==QQ_TLS_RECEIVING&&!br_ssl_engine_last_error(t->engine)){
  /* RFC 9112 9.8: authenticated complete Content-Length/chunked messages
   * survive an incomplete TLS close. Never accept EOF-delimited bodies. */
  if(qq_response_finish_framed_eof(&t->response))return fail(t,rc);
  qq_secret_clear(t->wire,sizeof(t->wire));t->anonymous_framed_eof=t->response.anonymous!=0;t->phase=QQ_TLS_DONE;return 1;
 }
 if(rc<0&&rc!=HB_TLS_SOCKET_TIMEOUT) return fail(t,rc);
 return 0;
}
