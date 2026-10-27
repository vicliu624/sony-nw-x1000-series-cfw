/* Entirely in-memory, fixed test keys/entropy/time. Never a deployed client. */
#include "bearssl.h"
#include <string.h>
#include <unistd.h>
#include <assert.h>
#ifdef HB_HTTPS_CONTROLLER
#include "../runtime/store/https_fetch.h"
#include <stdlib.h>
#include <fcntl.h>
extern void hb_download_test_fault(int,int);
#endif
#ifdef HB_TLS_LOCAL_CONNECT
#include "../runtime/store/connect_step.h"
#include <sys/un.h>
#include <stdio.h>
#include <errno.h>
#ifdef HB_TLS_LOOPBACK_CONNECT
#include <netinet/in.h>
#include <arpa/inet.h>
#else
extern int __real_connect(int,const struct sockaddr *,socklen_t);
int __wrap_connect(int fd,const struct sockaddr *address,socklen_t size){
 int result=__real_connect(fd,address,size);if(!result){errno=EINPROGRESS;return -1;}return result;
}
#endif
#endif
#include "../runtime/store/http_response.h"
#include "fixture_ta.h"
#include "chain-rsa.h"
#include "key-rsa.h"
#include "fixture_time.h"
#ifdef HB_TLS_SOCKETPAIR
#include "../runtime/store/tls_socket_step.h"
#include <sys/socket.h>
static int pair[2];
static struct hb_transfer_deadline transfer_deadline;
static unsigned long long original_end;
#ifdef HB_TLS_LOCAL_CONNECT
static int local_connection(int number){
#ifdef HB_TLS_LOOPBACK_CONNECT
 (void)number;struct sockaddr_in address;memset(&address,0,sizeof address);address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);int family=AF_INET;
#else
 struct sockaddr_un address;memset(&address,0,sizeof address);address.sun_family=AF_UNIX;
 int length=snprintf(address.sun_path+1,sizeof address.sun_path-1,"hb-cfw-%ld-%d",(long)getpid(),number);
 if(length<0||length>=(int)sizeof address.sun_path-1)return -1;
 int family=AF_UNIX;
#endif
 int listener=socket(family,SOCK_STREAM,0);if(listener<0)return -1;
 if(bind(listener,(const struct sockaddr *)&address,sizeof address)||listen(listener,4)){close(listener);return -1;}
#ifdef HB_TLS_LOOPBACK_CONNECT
 socklen_t address_size=sizeof address;if(getsockname(listener,(struct sockaddr *)&address,&address_size)||address.sin_addr.s_addr!=htonl(INADDR_LOOPBACK)||!address.sin_port){close(listener);return -1;}
#endif
 struct hb_connect connection;hb_connect_init(&connection);volatile int stop=0;
 int result=hb_connect_begin(&connection,family,(const struct sockaddr *)&address,sizeof address,&transfer_deadline,&stop);
 for(unsigned i=0;result==0&&i<1000;i++)result=hb_connect_step(&connection,0);
 if(result!=1){hb_connect_release(&connection);close(listener);return -1;}
 pair[0]=hb_connect_take(&connection);pair[1]=accept(listener,0,0);
 int closed=close(listener);
 if(pair[0]<0||pair[1]<0||closed||hb_connect_release(&connection))return -1;
#ifdef HB_TLS_LOOPBACK_CONNECT
 struct sockaddr_in remote;socklen_t remote_size=sizeof remote;
 if(getpeername(pair[0],(struct sockaddr *)&remote,&remote_size)||remote.sin_addr.s_addr!=htonl(INADDR_LOOPBACK))return -1;
#endif
 assert(transfer_deadline.end==original_end);return 0;
}
#endif
#endif
#ifdef HB_TLS_PLATFORM_INPUTS
#include "../runtime/store/tls_platform.h"
#endif
static br_ssl_client_context client;
static br_ssl_server_context server;
static br_x509_minimal_context verifier;
static unsigned char client_buffer[BR_SSL_BUFSIZE_BIDI],server_buffer[BR_SSL_BUFSIZE_BIDI];
static int transfer(br_ssl_engine_context *from,br_ssl_engine_context *to){
#ifdef HB_TLS_SOCKETPAIR
 volatile int stop=0;
 int a=hb_tls_socket_deadline_step(from,from==&client.eng?pair[0]:pair[1],&transfer_deadline,0,&stop);
 int b=hb_tls_socket_deadline_step(to,to==&client.eng?pair[0]:pair[1],&transfer_deadline,0,&stop);
 assert(transfer_deadline.end==original_end);
 return a==HB_TLS_SOCKET_PROGRESS||b==HB_TLS_SOCKET_PROGRESS;
#else
 size_t n,m;unsigned char *source=br_ssl_engine_sendrec_buf(from,&n),*dest=br_ssl_engine_recvrec_buf(to,&m);
 if(!n||!m)return 0;
 if(n>m)n=m;
 if(n>137)n=137;
 memcpy(dest,source,n);br_ssl_engine_sendrec_ack(from,n);br_ssl_engine_recvrec_ack(to,n);return 1;
#endif
}
struct body_sink {unsigned used;unsigned char bytes[3];};
static const char *response_text(int which){
 return which==4?"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabd":
  which==5?"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nabc":
  which==6?"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nab":
  which==7?"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\na\r\n2\r\nbc\r\n0\r\n\r\n":
  "HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc";
}
static int body_write(void *context,const unsigned char *data,unsigned n){
 struct body_sink *sink=context;if(!n||sink->used>=3)return -1;sink->bytes[sink->used++]=*data;return 1;
}
static int http_exchange(int which){
 static const unsigned char digest[32]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
 const char *response=response_text(which);
 size_t n;unsigned char *out=br_ssl_engine_sendapp_buf(&server.eng,&n);unsigned length=(unsigned)strlen(response);
 if(!out||n<length)return 41;
 memcpy(out,response,length);br_ssl_engine_sendapp_ack(&server.eng,length);br_ssl_engine_flush(&server.eng,0);
 struct body_sink sink={0};struct hb_download_stream body;struct hb_http_response http;
 if(hb_download_stream_init(&body,3,digest,&sink,body_write,0)||hb_http_response_init(&http,&body))return 42;
 int result=0;
 for(unsigned i=0;i<1000;i++){
  unsigned char *received=br_ssl_engine_recvapp_buf(&client.eng,&n);
  if(n){result=hb_http_response_push(&http,received,(unsigned)n);br_ssl_engine_recvapp_ack(&client.eng,n);if(result)break;}
  if(!transfer(&server.eng,&client.eng))break;
 }
 if(!result)result=hb_http_response_finish(&http);
 int expected=which==4?HB_DOWNLOAD_HASH:which==5?HB_HTTP_FRAMING_ERROR:which==6?HB_HTTP_TRUNCATED:0;
 if(result!=expected)return 43;
 if(expected)return body.state==HB_DOWNLOAD_FAILED?0:44;
 return body.state==HB_DOWNLOAD_VERIFIED&&sink.used==3&&!memcmp(sink.bytes,"abc",3)?0:45;
}
#ifdef HB_HTTPS_CONTROLLER
static int controller_exchange(int which){
 static const unsigned char digest[32]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
 struct hb_download_file file;volatile int stop=0;hb_download_file_init(&file);
 const char *key=which==14?"file-sync":which==15?"dir-sync":which==16?"close-error":"fixture";
 if(hb_download_file_begin(&file,getenv("HB_HTTP_CACHE"),key,3,digest,4096,&stop))return 70;
 if(which==14)hb_download_test_fault(4,1);
 if(which==15)hb_download_test_fault(4,2);
 if(which==16)hb_download_test_fault(5,1);
 struct hb_https_fetch fetch;
 if(which==0){
  const char *hosts[]={"localhost","other.invalid","localhost\r\nX-Injected: yes"};
  const char *paths[]={"/fixture\r\nX-Injected: yes","/fixture","/fixture"};
  for(unsigned i=0;i<3;i++){
   if(hb_https_fetch_init(&fetch,&client.eng,pair[0],&file,&transfer_deadline,hosts[i],443,paths[i])!=HB_HTTPS_INPUT||file.state==HB_FETCH_READY)return 81;
   if(hb_download_file_discard(&file))return 82;
   hb_download_file_init(&file);
   if(hb_download_file_begin(&file,getenv("HB_HTTP_CACHE"),"fixture",3,digest,4096,&stop))return 83;
  }
 }
 if(hb_https_fetch_init_url(&fetch,&client.eng,pair[0],&file,&transfer_deadline,which==1?"HTTPS://WRONG.INVALID/fixture":"HTTPS://LOCALHOST/fixture#not-sent"))return 71;
 if(which==8)stop=1;
 if((which==9||which==10)&&hb_transfer_deadline_init(&transfer_deadline,which==9?0:2))return 84;
 if(which==13)transfer_deadline.valid=0; /* Explicit clock-state error fixture. */
 unsigned long long controller_end=transfer_deadline.end;
 char request[2048];unsigned used=0;int seen=0,sent=0,closing=0,result=0,abrupt=0;
 for(unsigned tick=0;tick<100000;tick++){
  result=hb_https_fetch_step(&fetch,which==10?1:0);if(result)break;
  assert(transfer_deadline.end==controller_end);
  if(which==12&&file.body.received)stop=1;
  if(which==10)continue; /* Peer deliberately never services its socket. */
  unsigned state=br_ssl_engine_current_state(&server.eng);size_t n;
  if(state&BR_SSL_RECVAPP){
   unsigned char *input=br_ssl_engine_recvapp_buf(&server.eng,&n);if(n>=sizeof request-used)return 72;
   memcpy(request+used,input,n);used+=(unsigned)n;request[used]=0;br_ssl_engine_recvapp_ack(&server.eng,n);
   if(strstr(request,"\r\n\r\n")){
    if(strncmp(request,"GET /fixture HTTP/1.1\r\n",sizeof("GET /fixture HTTP/1.1\r\n")-1)||!strstr(request,"\r\nHost: localhost\r\n")||!strstr(request,"\r\nAccept-Encoding: identity\r\n"))return 73;
    seen=1;
   }
  }
  state=br_ssl_engine_current_state(&server.eng);
  if(which==11&&seen&&!abrupt){if(shutdown(pair[1],SHUT_WR))return 85;abrupt=1;}
  if(which!=11&&seen&&!sent&&(state&BR_SSL_SENDAPP)){
   const char *response=response_text(which);unsigned length=(unsigned)strlen(response);
   unsigned char *out=br_ssl_engine_sendapp_buf(&server.eng,&n);if(n<length)return 74;
   memcpy(out,response,length);br_ssl_engine_sendapp_ack(&server.eng,length);br_ssl_engine_flush(&server.eng,0);sent=1;
  }else if(sent&&!closing&&(state&BR_SSL_SENDAPP)){br_ssl_engine_close(&server.eng);closing=1;}
  (void)hb_tls_socket_deadline_step(&server.eng,pair[1],&transfer_deadline,0,&stop);
 }
 int expected=which>=1&&which<=3?HB_HTTPS_TLS:which==4?HB_DOWNLOAD_HASH:which==5?HB_HTTP_FRAMING_ERROR:which==6?HB_HTTP_TRUNCATED:
  which==8||which==12?HB_DOWNLOAD_CANCELLED:which==9||which==10?HB_HTTPS_DEADLINE:which==11?HB_HTTPS_EOF:which==13?HB_HTTPS_CLOCK:which>=14?HB_FETCH_RETAINED:1;
 if(result!=expected)return 75;
 if(result==1){
  if(file.state!=HB_FETCH_READY||fetch.phase!=HB_HTTPS_DONE)return 76;
  unsigned char bytes[4];int fd=open(file.path,O_RDONLY);if(fd<0||read(fd,bytes,4)!=3||memcmp(bytes,"abc",3)||close(fd))return 77;
 }else{
  if(file.state==HB_FETCH_READY||fetch.phase!=HB_HTTPS_FAILED||hb_https_fetch_step(&fetch,0)!=result)return 78;
  if(which<=3&&(seen||fetch.tls_error!=(which==1?BR_ERR_X509_BAD_SERVER_NAME:which==2?BR_ERR_X509_NOT_TRUSTED:BR_ERR_X509_EXPIRED)))return 79;
 }
 if(stop){if(hb_download_file_discard(&file)!=HB_DOWNLOAD_CANCELLED||file.fd!=-1)return 86;stop=0;}
 if(which>=14){
  if(file.state!=HB_FETCH_REVIEW||file.fd!=-1||hb_download_file_discard(&file)!=HB_FETCH_RETAINED)return 87;
  if(which==14){
   hb_download_test_fault(0,0);
   if(hb_download_file_recheck(&file)||file.state!=HB_FETCH_READY||fetch.phase!=HB_HTTPS_FAILED||hb_https_fetch_step(&fetch,0)!=HB_FETCH_RETAINED)return 88;
  }
  return 0;
 }
 if(hb_download_file_discard(&file))return 80;
 return 0;
}
#endif
static int scenario(int which){
 unsigned char seed[48];for(unsigned i=0;i<48;i++)seed[i]=(unsigned char)i;
#ifdef HB_TLS_PLATFORM_INPUTS
 volatile int stop=0;struct hb_tls_time now;
 if(hb_tls_seed(seed,&stop)||hb_tls_current_time(&now))return 11;
#endif
 br_ssl_client_init_full(&client,&verifier,which==2?0:TAs,which==2?0:TAs_NUM);
 br_ssl_engine_set_versions(&client.eng,BR_TLS12,BR_TLS12);
 br_ssl_engine_set_buffer(&client.eng,client_buffer,sizeof client_buffer,1);
 br_ssl_engine_inject_entropy(&client.eng,seed,sizeof seed);
#ifdef HB_TLS_PLATFORM_INPUTS
 br_x509_minimal_set_time(&verifier,which==3?FIXTURE_EXPIRED_DAYS:now.days,which==3?0:now.seconds);
#else
 br_x509_minimal_set_time(&verifier,which==3?FIXTURE_EXPIRED_DAYS:FIXTURE_VALID_DAYS,0);
#endif
 br_ssl_server_init_full_rsa(&server,CHAIN,CHAIN_LEN,&RSA);
 br_ssl_engine_set_versions(&server.eng,BR_TLS12,BR_TLS12);
 br_ssl_engine_set_buffer(&server.eng,server_buffer,sizeof server_buffer,1);
#ifdef HB_TLS_PLATFORM_INPUTS
 if(hb_tls_seed(seed,&stop))return 12;
#else
 seed[0]=123;
#endif
 br_ssl_engine_inject_entropy(&server.eng,seed,sizeof seed);
 {volatile unsigned char *p=seed;for(unsigned i=0;i<sizeof seed;i++)p[i]=0;}
 if(!br_ssl_client_reset(&client,which==1?"wrong.invalid":"localhost",0)||!br_ssl_server_reset(&server))return 10;
#ifdef HB_HTTPS_CONTROLLER
 return controller_exchange(which);
#endif
 int complete=0;
 for(unsigned i=0;i<100000;i++){
  if(br_ssl_engine_last_error(&client.eng)||br_ssl_engine_last_error(&server.eng))break;
  if((br_ssl_engine_current_state(&client.eng)&BR_SSL_SENDAPP)&&
    (br_ssl_engine_current_state(&server.eng)&BR_SSL_SENDAPP)){complete=1;break;}
  int moved=transfer(&client.eng,&server.eng);moved+=transfer(&server.eng,&client.eng);
  if(!moved)break;
 }
 int error=br_ssl_engine_last_error(&client.eng);
 if(which>=1&&which<=3)return !complete&&error==(which==1?BR_ERR_X509_BAD_SERVER_NAME:which==2?BR_ERR_X509_NOT_TRUSTED:BR_ERR_X509_EXPIRED)?0:20+which;
 if(!complete||error)return 30;
 static const char payload[]="GET /fixture HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";size_t n;
 unsigned char *out=br_ssl_engine_sendapp_buf(&client.eng,&n);if(!out||n<sizeof payload-1)return 31;
 memcpy(out,payload,sizeof payload-1);br_ssl_engine_sendapp_ack(&client.eng,sizeof payload-1);br_ssl_engine_flush(&client.eng,0);
 for(unsigned i=0;i<1000;i++){
  unsigned char *received=br_ssl_engine_recvapp_buf(&server.eng,&n);
  if(n){int ok=n==sizeof payload-1&&!memcmp(received,payload,n);br_ssl_engine_recvapp_ack(&server.eng,n);return ok?http_exchange(which):32;}
  if(!transfer(&client.eng,&server.eng))break;
 }
 return 33;
}
int main(void){
#ifdef HB_HTTPS_CONTROLLER
 const int scenarios=17;
#else
 const int scenarios=8;
#endif
 for(int i=0;i<scenarios;i++){
#ifdef HB_TLS_SOCKETPAIR
  if(hb_transfer_deadline_init(&transfer_deadline,30000))return 60;
  original_end=transfer_deadline.end;
#ifdef HB_TLS_LOCAL_CONNECT
  if(local_connection(i))return 89;
#else
  if(socketpair(AF_UNIX,SOCK_STREAM,0,pair))return 50;
#endif
#endif
  int result=scenario(i);
#ifdef HB_TLS_SOCKETPAIR
  if(!result&&(i==0||i==7)){
#ifndef HB_HTTPS_CONTROLLER
   volatile int stop=1;
   if(hb_tls_socket_step(&client.eng,pair[0],0,&stop)!=HB_TLS_SOCKET_CANCELLED)result=51;
   stop=0;
   if(i==0){
    struct hb_transfer_deadline stalled;int expired=0;
    if(hb_transfer_deadline_init(&stalled,2))return 61;
    unsigned long long end=stalled.end;
    for(unsigned tries=0;tries<32;tries++){
     int result=hb_tls_socket_deadline_step(&client.eng,pair[0],&stalled,1,&stop);
     assert(stalled.end==end);
     if(result==HB_TLS_SOCKET_DEADLINE){expired=1;break;}
     if(result!=HB_TLS_SOCKET_TIMEOUT&&result!=HB_TLS_SOCKET_WAIT)return 62;
    }
    if(!expired)return 63;
    if(shutdown(pair[1],SHUT_WR)||hb_tls_socket_step(&client.eng,pair[0],100,&stop)!=HB_TLS_SOCKET_EOF)result=52;
   }else{
    br_ssl_engine_close(&server.eng);int closed=0;
    for(unsigned tick=0;tick<1000;tick++){
     int a=hb_tls_socket_step(&server.eng,pair[1],0,&stop);
     int b=hb_tls_socket_step(&client.eng,pair[0],0,&stop);
     if(a==HB_TLS_SOCKET_CLOSED&&b==HB_TLS_SOCKET_CLOSED){closed=1;break;}
     if(a<0&&a!=HB_TLS_SOCKET_TIMEOUT){result=54;break;}
     if(b<0&&b!=HB_TLS_SOCKET_TIMEOUT){result=55;break;}
    }
    if(!closed)result=56;
    if(closed&&(br_ssl_engine_last_error(&client.eng)||br_ssl_engine_last_error(&server.eng)))result=57;
   }
#endif
  }
  if(close(pair[0])||close(pair[1]))result=53;
#endif
  if(result)return result;
 }
 static const char result[]="TLS12/HTTP/body passed; certificate, length, hash and truncation refusals passed\n";
 return write(1,result,sizeof result-1)==(long)(sizeof result-1)?0:40;
}
