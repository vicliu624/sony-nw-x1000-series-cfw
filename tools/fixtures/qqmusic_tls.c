/* Local test CA and synthetic HTTP only. Never a production trust setup. */
#include "../../runtime/apps/qqmusic/qqmusic_tls.h"
#include "../../runtime/apps/qqmusic/qqmusic_cgi.h"
#include "../../runtime/apps/qqmusic/qqmusic_credential.h"
#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <arpa/inet.h>
static struct qq_tls_transaction transaction;
static br_ssl_client_context client;
static br_x509_minimal_context verifier;
static br_x509_decoder_context decoder;
static unsigned char tls_buffer[BR_SSL_BUFSIZE_BIDI],der[8192],dn[1024],body[1024];
static size_t dn_bytes;
static struct qq_json json;
static struct {size_t bytes;unsigned finished,aborted;} media;
static int media_write(void *unused,const unsigned char *p,size_t n) {
 size_t i;(void)unused;assert(n&&n<=4096);
 for(i=0;i<n;i++) assert(p[i]==(unsigned char)((media.bytes+i)%251));
 media.bytes+=n;return 0;
}
static int media_finish(void *unused,uint64_t bytes,const unsigned char *digest) {
 (void)unused;(void)digest;assert(bytes==media.bytes);media.finished++;return 0;
}
static void media_abort(void *unused) {(void)unused;media.aborted++;media.bytes=0;}
static void append_dn(void *unused,const void *data,size_t n) {
 (void)unused;assert(n<=sizeof(dn)-dn_bytes);memcpy(dn+dn_bytes,data,n);dn_bytes+=n;
}
int main(int argc,char **argv) {
 br_x509_trust_anchor anchor;struct qq_cookie_jar jar,before;
 struct qq_request request;struct hb_transfer_deadline deadline;
 unsigned char seed[48];struct sockaddr_in address;int fd,cert,rc,expected,mode;
 unsigned long port,now;size_t i;ssize_t bytes;volatile int stop=0;
 unsigned long long original_end;int complete_seen=0;
 assert(argc==6);port=strtoul(argv[1],0,10);now=strtoul(argv[3],0,10);
 expected=atoi(argv[4]);mode=atoi(argv[5]);assert(port&&port<=65535);
 int media_mode=mode==13||mode==14||mode==18,cgi_mode=mode>=11&&!media_mode&&mode!=19;
 cert=open(argv[2],O_RDONLY);assert(cert>=0);bytes=read(cert,der,sizeof(der));assert(bytes>0&&bytes<(ssize_t)sizeof(der));assert(close(cert)==0);
 br_x509_decoder_init(&decoder,append_dn,0);br_x509_decoder_push(&decoder,der,(size_t)bytes);
 assert(br_x509_decoder_last_error(&decoder)==0&&br_x509_decoder_get_pkey(&decoder));
 memset(&anchor,0,sizeof(anchor));anchor.dn.data=dn;anchor.dn.len=dn_bytes;
 anchor.flags=BR_X509_TA_CA;anchor.pkey=*br_x509_decoder_get_pkey(&decoder);
 br_ssl_client_init_full(&client,&verifier,&anchor,1);
 br_ssl_engine_set_versions(&client.eng,BR_TLS12,BR_TLS12);
 br_ssl_engine_set_buffer(&client.eng,tls_buffer,sizeof(tls_buffer),1);
 for(i=0;i<sizeof(seed);i++) seed[i]=(unsigned char)(i+11);
 br_ssl_engine_inject_entropy(&client.eng,seed,sizeof(seed));
 br_x509_minimal_set_time(&verifier,719528u+(unsigned)(now/86400),(unsigned)(now%86400));
 assert(br_ssl_client_reset(&client,media_mode?"isure.stream.qqmusic.qq.com":cgi_mode?"u.y.qq.com":"graph.qq.com",0));
 fd=socket(AF_INET,SOCK_STREAM,0);assert(fd>=0);
 memset(&address,0,sizeof(address));address.sin_family=AF_INET;
 address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);address.sin_port=htons((unsigned short)port);
 assert(connect(fd,(const struct sockaddr *)&address,sizeof(address))==0);
 qq_cookie_clear(&jar);before=jar;
 if(cgi_mode) {
  const char *comm="{\"ct\":\"19\",\"cv\":\"2201\",\"tmeLoginType\":\"2\",\"guid\":\"synthetic-only\"}";
  assert(qq_build_login_cgi(&request,&json,comm,strlen(comm),"synthetic_code")==0);
 } else assert(qq_build_authorize(&request,"o00123456","synthetic","random-state","synthetic-ui",now*1000ULL)==0);
 assert(hb_transfer_deadline_init(&deadline,mode==2?30:mode==10?500:media_mode?15000:5000)==0);
 original_end=deadline.end;
 if(media_mode) {
  struct qq_resource resource;struct qq_response_sink callbacks={0,media_write,media_finish,media_abort};
  const char *url="https://isure.stream.qqmusic.qq.com/M800MEDIA02.mp3?vkey=synthetic";
  memset(&resource,0,sizeof(resource));memcpy(resource.url,url,strlen(url)+1);
  assert(qq_tls_begin_stream(&transaction,&client.eng,fd,&deadline,&stop,&resource,4*1024*1024,callbacks)==0);
 } else assert(qq_tls_begin(&transaction,&client.eng,fd,&deadline,&stop,&request,&jar,now,body,sizeof(body))==0);
 rc=0;for(i=0;!rc&&i<100000;i++) {
  if(mode==1&&transaction.phase==QQ_TLS_RECEIVING) stop=1;
  if(transaction.response.phase==QQ_RX_COMPLETE) complete_seen=1;
  if(mode==8&&transaction.response.body_bytes) stop=1;
  rc=qq_tls_step(&transaction,5);
  assert(deadline.end==original_end);
 }
 assert(rc!=0);
 if(expected) {
  assert(rc==1&&transaction.phase==QQ_TLS_DONE);
  if(media_mode) assert(media.bytes==3*1024*1024+17&&media.finished==1&&!media.aborted);
  else if(cgi_mode) {
   struct qq_credential credential;uint64_t code;
   int auth=qq_credential_parse(&json,(const char *)body,transaction.response.body_bytes,&credential,&code);
   if(mode!=12) assert(auth==0&&credential.musicid==9007199254740993ULL&&!strcmp(credential.musickey,"synthetic_key"));
   else assert(auth==QQ_AUTH_DEVICE_LIMIT&&code==20279&&!credential.musicid);
   qq_credential_clear(&credential);
  } else assert(transaction.response.body_bytes==5&&!memcmp(body,"hello",5));
  if(!media_mode) assert(memcmp(&jar,&before,sizeof(jar)));
  else assert(!memcmp(&jar,&before,sizeof(jar)));
 } else {
  assert(rc<0&&transaction.phase==QQ_TLS_FAILED&&!memcmp(&jar,&before,sizeof(jar)));
  for(i=0;i<sizeof(body);i++) assert(body[i]==0);
  if(mode==3) assert(br_ssl_engine_last_error(&client.eng)==BR_ERR_X509_NOT_TRUSTED);
  if(mode==4) assert(br_ssl_engine_last_error(&client.eng)==BR_ERR_X509_BAD_SERVER_NAME);
  if(mode==5) assert(br_ssl_engine_last_error(&client.eng)==BR_ERR_X509_EXPIRED);
  if(mode==17||mode==19) assert(transaction.error==HB_TLS_SOCKET_EOF&&!br_ssl_engine_last_error(&client.eng));
  if(mode==7) assert(transaction.error==-6&&!br_ssl_engine_last_error(&client.eng));
  if(mode==1) assert(stop&&transaction.error==-2);
  if(mode==8) assert(stop&&complete_seen&&transaction.error==-2);
  if(mode==2) assert(transaction.error==-3||transaction.error==HB_TLS_SOCKET_DEADLINE);
  if(mode==10) assert(complete_seen&&(transaction.error==-3||transaction.error==HB_TLS_SOCKET_DEADLINE));
  if(mode==18) assert(media.aborted==1&&!media.finished&&transaction.error==HB_TLS_SOCKET_EOF);
 }
 for(i=0;i<sizeof(transaction.wire);i++) assert(transaction.wire[i]==0);
 assert(close(fd)==0);qq_tls_cancel(&transaction);qq_cookie_clear(&jar);
 return 0;
}
