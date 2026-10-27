#include "https_fetch.h"
#include "https_url.h"
#include <string.h>
static int fail(struct hb_https_fetch *f,int error){
 f->phase=HB_HTTPS_FAILED;f->error=error;
 if(f->file){f->file->body.state=HB_DOWNLOAD_FAILED;f->file->body.error=error;if(f->file->state==HB_FETCH_READY)f->file->state=HB_FETCH_OPEN;}
 return error;
}
static int budget(struct hb_https_fetch *f){
 if(f->file->body.stop&&*f->file->body.stop)return HB_DOWNLOAD_CANCELLED;
 unsigned wait;int result=hb_transfer_deadline_remaining(f->deadline,&wait);
 return result<0?HB_HTTPS_CLOCK:result?0:HB_HTTPS_DEADLINE;
}
static int append(struct hb_https_fetch *f,const char *text){
 for(unsigned i=0;text[i];i++){if(f->request_bytes==sizeof f->request)return -1;f->request[f->request_bytes++]=text[i];}return 0;
}
int hb_https_fetch_init(struct hb_https_fetch *f,br_ssl_engine_context *engine,int fd,
 struct hb_download_file *file,struct hb_transfer_deadline *deadline,const char *host,unsigned port,const char *path){
 if(!f)return HB_HTTPS_INPUT;
 f->file=file;f->phase=HB_HTTPS_FAILED;f->error=HB_HTTPS_INPUT;f->tls_error=0;
 if(!engine||fd<0||!file||file->state!=HB_FETCH_OPEN||!deadline||!deadline->valid||!host||!path||!port||port>65535)return HB_HTTPS_INPUT;
 unsigned n=0;for(;n<=253&&host[n];n++)if(!((host[n]>='a'&&host[n]<='z')||(host[n]>='A'&&host[n]<='Z')||(host[n]>='0'&&host[n]<='9')||host[n]=='-'||host[n]=='.'))return fail(f,HB_HTTPS_INPUT);
 if(!n||n>253||host[0]=='.'||host[n-1]=='.')return fail(f,HB_HTTPS_INPUT);
 const char *bound=br_ssl_engine_get_server_name(engine);if(!bound||strcmp(bound,host))return fail(f,HB_HTTPS_INPUT);
 n=0;for(;n<=2048&&path[n];n++)if((unsigned char)path[n]<33||(unsigned char)path[n]>126||path[n]=='#')return fail(f,HB_HTTPS_INPUT);
 if(!n||n>2048||path[0]!='/'||path[1]=='/')return fail(f,HB_HTTPS_INPUT);
 f->engine=engine;f->fd=fd;f->deadline=deadline;f->request_bytes=f->sent=0;
 if(append(f,"GET ")||append(f,path)||append(f," HTTP/1.1\r\nHost: ")||append(f,host))return fail(f,HB_HTTPS_INPUT);
 if(port!=443){char digits[7],reverse[5];unsigned used=0;while(port){reverse[used++]=(char)('0'+port%10);port/=10;}digits[0]=':';for(unsigned i=0;i<used;i++)digits[i+1]=reverse[used-i-1];digits[used+1]=0;if(append(f,digits))return fail(f,HB_HTTPS_INPUT);}
 if(append(f,"\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n")||hb_http_response_init(&f->response,&file->body))return fail(f,HB_HTTPS_INPUT);
 if(f->request_bytes>=sizeof f->request)return fail(f,HB_HTTPS_INPUT);
 f->request[f->request_bytes]=0; /* Terminator is not sent on the wire. */
 f->response.allow_redirects=1;
 f->phase=HB_HTTPS_REQUEST;f->error=0;return 0;
}
int hb_https_fetch_init_url(struct hb_https_fetch *f,br_ssl_engine_context *engine,int fd,
 struct hb_download_file *file,struct hb_transfer_deadline *deadline,const char *text){
 if(!f)return HB_HTTPS_INPUT;
 struct hb_https_url url;
 if(hb_https_url_parse(text,&url)){
  f->file=file;f->phase=HB_HTTPS_FAILED;f->error=HB_HTTPS_INPUT;f->tls_error=0;
  return file?fail(f,HB_HTTPS_INPUT):HB_HTTPS_INPUT;
 }
 return hb_https_fetch_init(f,engine,fd,file,deadline,url.host,url.port,url.path);
}
int hb_https_fetch_step(struct hb_https_fetch *f,unsigned cap){
 if(!f)return HB_HTTPS_INPUT;
 if(f->phase==HB_HTTPS_FAILED)return f->error;
 if(f->phase==HB_HTTPS_DONE)return 1;
 if(f->phase==HB_HTTPS_REDIRECT)return 2;
 if(cap>1000)return fail(f,HB_HTTPS_INPUT);
 int result=budget(f);if(result)return fail(f,result);
 if(br_ssl_engine_last_error(f->engine)){f->tls_error=br_ssl_engine_last_error(f->engine);return fail(f,HB_HTTPS_TLS);}
 unsigned state=br_ssl_engine_current_state(f->engine);size_t n;
 if(state&BR_SSL_CLOSED){
  if(f->phase==HB_HTTPS_REQUEST)return fail(f,HB_HTTP_TRUNCATED);
  if(f->response.state!=HB_HTTP_DONE){result=hb_http_response_finish(&f->response);if(result)return fail(f,result);}
  result=budget(f);if(result)return fail(f,result);
  result=hb_download_file_finish(f->file);if(result)return fail(f,result);
  result=budget(f);if(result)return fail(f,result);
  f->phase=HB_HTTPS_DONE;return 1;
 }
 if(f->phase==HB_HTTPS_REQUEST&&(state&BR_SSL_SENDAPP)){
  unsigned char *out=br_ssl_engine_sendapp_buf(f->engine,&n);unsigned left=f->request_bytes-f->sent;
  if(!out||!n)return fail(f,HB_HTTPS_TLS);
  if(n>left)n=left;
  memcpy(out,f->request+f->sent,n);br_ssl_engine_sendapp_ack(f->engine,n);f->sent+=(unsigned)n;
  if(f->sent==f->request_bytes){br_ssl_engine_flush(f->engine,0);f->phase=HB_HTTPS_RESPONSE;}
  result=budget(f);return result?fail(f,result):0;
 }
 if(state&BR_SSL_RECVAPP){
  if(f->phase!=HB_HTTPS_RESPONSE)return fail(f,HB_HTTP_FRAMING_ERROR);
  unsigned char *input=br_ssl_engine_recvapp_buf(f->engine,&n);if(!input||!n)return fail(f,HB_HTTPS_TLS);
  if(n>4096)n=4096;
  result=hb_http_response_push(&f->response,input,(unsigned)n);br_ssl_engine_recvapp_ack(f->engine,n);if(result)return fail(f,result);
  if(f->response.state==HB_HTTP_REDIRECT){f->phase=HB_HTTPS_REDIRECT;return 2;}
  if(f->response.state==HB_HTTP_COMPLETE){result=hb_http_response_finish(&f->response);if(result)return fail(f,result);f->phase=HB_HTTPS_CLOSING;}
  result=budget(f);return result?fail(f,result):0;
 }
 result=hb_tls_socket_deadline_step(f->engine,f->fd,f->deadline,cap,f->file->body.stop);
 if(result==HB_TLS_SOCKET_DEADLINE)return fail(f,HB_HTTPS_DEADLINE);
 if(result==HB_TLS_SOCKET_CLOCK)return fail(f,HB_HTTPS_CLOCK);
 if(result==HB_TLS_SOCKET_CANCELLED)return fail(f,HB_DOWNLOAD_CANCELLED);
 if(result==HB_TLS_SOCKET_EOF){
  /* Complete length/chunk framing plus the expected hash authenticates payload
   * even when a real HTTPS CDN omits close_notify. EOF framing still rejects. */
  if(f->phase==HB_HTTPS_CLOSING&&f->response.state==HB_HTTP_DONE&&(f->response.has_length||f->response.chunked)){
   result=hb_download_file_finish(f->file);if(result)return fail(f,result);f->phase=HB_HTTPS_DONE;return 1;
  }
  return fail(f,HB_HTTPS_EOF);
 }
 if(result==HB_TLS_SOCKET_PROTOCOL){f->tls_error=br_ssl_engine_last_error(f->engine);return fail(f,HB_HTTPS_TLS);}
 if(result<0&&result!=HB_TLS_SOCKET_TIMEOUT)return fail(f,HB_HTTPS_IO);
 return 0;
}
