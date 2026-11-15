#include "../../runtime/apps/qqmusic/qqmusic_network.h"
#include "../../runtime/apps/qqmusic/qqmusic_image.h"
#ifdef QQ_LIVE_QIMEI
#include "../../runtime/apps/qqmusic/qqmusic_qimei.h"
#include "../../runtime/apps/qqmusic/qqmusic_identity.h"
static struct qq_identity identity;
static struct qq_json diagnostic_json;static char diagnostic_inner[8193];
static unsigned outer_json,inner_json,q16_bytes,q36_bytes;static uint64_t outer_code,inner_code;
static void diagnose_qimei(const struct qq_response *response){
 int node,data;char value[129];
 if(qq_json_parse(&diagnostic_json,(const char *)response->body,response->body_bytes))return;
 outer_json=1;node=qq_json_get(&diagnostic_json,0,"code");if(node>=0)qq_json_uint(&diagnostic_json,(unsigned)node,&outer_code);
 node=qq_json_get(&diagnostic_json,0,"data");
 if(node<0||qq_json_string(&diagnostic_json,(unsigned)node,diagnostic_inner,sizeof(diagnostic_inner)))goto done;
 if(qq_json_parse(&diagnostic_json,diagnostic_inner,strlen(diagnostic_inner)))goto done;
 inner_json=1;node=qq_json_get(&diagnostic_json,0,"code");if(node>=0)qq_json_uint(&diagnostic_json,(unsigned)node,&inner_code);
 data=qq_json_get(&diagnostic_json,0,"data");if(data<0)goto done;
 node=qq_json_get(&diagnostic_json,(unsigned)data,"q16");if(node>=0&&!qq_json_string(&diagnostic_json,(unsigned)node,value,sizeof(value)))q16_bytes=(unsigned)strlen(value);
 node=qq_json_get(&diagnostic_json,(unsigned)data,"q36");if(node>=0&&!qq_json_string(&diagnostic_json,(unsigned)node,value,sizeof(value)))q36_bytes=(unsigned)strlen(value);
done:qq_secret_clear(value,sizeof(value));qq_secret_clear(diagnostic_inner,sizeof(diagnostic_inner));qq_secret_clear(&diagnostic_json,sizeof(diagnostic_json));
}
#endif
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_network network;static br_x509_decoder_context decoder;static unsigned char der[8192],dn[2048];static size_t dn_bytes;static int dn_bad;
#ifndef QQ_LIVE_QIMEI
static unsigned short pixels[196*196];
#endif
static void append(void *unused,const void *p,size_t n){(void)unused;if(n>sizeof(dn)-dn_bytes){dn_bad=1;return;}memcpy(dn+dn_bytes,p,n);dn_bytes+=n;}
static int material(void *unused,struct qq_runtime_material *out){(void)unused;(void)out;return -1;}
#ifndef QQ_LIVE_QIMEI
static int save(const char *path,const void *data,size_t n){int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);size_t at=0;if(fd<0)return -1;while(at<n){ssize_t wrote=write(fd,(const unsigned char *)data+at,n-at);if(wrote<=0){close(fd);return -1;}at+=(size_t)wrote;}return close(fd);}
#endif
int main(int argc,char **argv){
 struct qq_network_config config;struct qq_cookie_jar jar;struct qq_request request;struct qq_response *response=0;br_x509_trust_anchor anchor;unsigned char seed[48];char text[512];unsigned i;int fd,rc=-1,status=0,n;ssize_t bytes;const struct qq_runtime_ops *ops;
#ifdef QQ_LIVE_QIMEI
 struct qq_qimei ids;struct hb_tls_time clock;char payload[1536],installation[33];static volatile int stopped;int valid=0,previous_phase=0,previous_rx=0,session_valid=0,session_status=0,session_result=-1,qimei_error=0,qimei_tls=0;size_t reply_bytes=0,previous_sent=0;
#else
 char cookie[1025];unsigned w=0,h=0;int valid_image=0,has_qrsig=0;
#endif
 if(argc!=4)return 64;
 fd=open(argv[1],O_RDONLY);if(fd<0)return 2;bytes=sony_read(fd,der,sizeof(der));close(fd);if(bytes<=0||(size_t)bytes>=sizeof(der))return 2;
 br_x509_decoder_init(&decoder,append,0);br_x509_decoder_push(&decoder,der,(size_t)bytes);if(dn_bad||!br_x509_decoder_isCA(&decoder)||br_x509_decoder_last_error(&decoder)||!br_x509_decoder_get_pkey(&decoder))return 2;
 memset(&anchor,0,sizeof(anchor));anchor.dn.data=dn;anchor.dn.len=dn_bytes;anchor.flags=BR_X509_TA_CA;anchor.pkey=*br_x509_decoder_get_pkey(&decoder);
 memset(&config,0,sizeof(config));config.anchors=&anchor;config.anchor_count=1;config.timeout_ms=20000;config.poll_ms=5;qq_cookie_clear(&jar);
 if(qq_network_init(&network,&config,0,material,0)||hb_tls_seed(seed,0))return 2;
#ifdef QQ_LIVE_QIMEI
 for(i=0;i<16;i++){static const char hex[]="0123456789abcdef";installation[2*i]=hex[seed[i]>>4];installation[2*i+1]=hex[seed[i]&15];}installation[32]=0;
 n=sony_snprintf(payload,sizeof(payload),"{\"androidId\":\"%s\",\"platformId\":1,\"appKey\":\"0AND0HD6FE4HY80F\",\"appVersion\":\"20.9.0.8\",\"beaconIdSrc\":\"\",\"brand\":\"Sony\",\"channelId\":\"10003505\",\"cid\":\"\",\"imei\":\"\",\"imsi\":\"\",\"mac\":\"\",\"model\":\"NW-X1060\",\"networkType\":\"wifi\",\"oaid\":\"\",\"osVersion\":\"Linux (Sony NW-X1060)\",\"qimei\":\"\",\"qimei36\":\"\",\"sdkVersion\":\"1.2.13.6\",\"targetSdkVersion\":\"\",\"audit\":\"\",\"userId\":\"{}\",\"packageId\":\"com.tencent.qqmusic\",\"deviceType\":\"Walkman\",\"sdkName\":\"\",\"reserved\":\"{}\"}",installation);
 if(n<=0||(size_t)n>=sizeof(payload)||hb_tls_current_time(&clock)||qq_qimei_request(&request,payload,(size_t)n,clock.unix_seconds,&stopped,0))return 2;
 qq_secret_clear(payload,sizeof(payload));
#else
 if(qq_build_qr(&request,(uint32_t)seed[0]|(uint32_t)seed[1]<<8|(uint32_t)seed[2]<<16|(uint32_t)seed[3]<<24))return 2;
#endif
 qq_secret_clear(seed,sizeof(seed));ops=qq_network_operations(&network);
 rc=ops->start(ops->context,&request,&jar,1);qq_secret_clear(&request,sizeof(request));
 for(i=0;!rc&&i<200000;i++){
#ifdef QQ_LIVE_QIMEI
  previous_phase=(int)network.transaction.phase;previous_rx=(int)network.transaction.response.phase;
  previous_sent=network.transaction.sent;
  if(network.transaction.response.head.status){status=(int)network.transaction.response.head.status;reply_bytes=network.transaction.response.body_bytes;}
#endif
  rc=ops->poll(ops->context,&response);
 }
#ifdef QQ_LIVE_QIMEI
 if(rc==1&&response){status=(int)response->head.status;reply_bytes=response->body_bytes;valid=qq_qimei_accept(response,&ids)==0;diagnose_qimei(response);}
 qimei_error=network.error;qimei_tls=network.tls_error;
 if(valid){
  ops->cancel(ops->context);qq_cookie_clear(&jar);
  n=sony_snprintf(payload,sizeof(payload),"{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"QIMEI36\":\"\",\"OpenUDID\":\"%s\",\"udid\":\"%s\",\"aid\":\"%s\",\"phonetype\":\"Sony NW-X1060\",\"os_ver\":\"Linux\",\"chid\":\"10003505\",\"tmeAppID\":\"qqmusic\"}",installation,installation,installation);
  if(n<=0||(size_t)n>=sizeof(payload)||qq_identity_init(&identity,payload,installation,&stopped,0)||qq_identity_bind_qimei(&identity,ids.q36))return 2;
  qq_secret_clear(payload,sizeof(payload));qq_secret_clear(installation,sizeof(installation));
  fd=open(argv[3],O_RDONLY);if(fd<0)return 2;bytes=sony_read(fd,der,sizeof(der));close(fd);if(bytes<=0||(size_t)bytes>=sizeof(der))return 2;
  dn_bytes=0;dn_bad=0;br_x509_decoder_init(&decoder,append,0);br_x509_decoder_push(&decoder,der,(size_t)bytes);
  if(dn_bad||!br_x509_decoder_isCA(&decoder)||br_x509_decoder_last_error(&decoder)||!br_x509_decoder_get_pkey(&decoder))return 2;
  anchor.dn.data=dn;anchor.dn.len=dn_bytes;anchor.pkey=*br_x509_decoder_get_pkey(&decoder);
  if(qq_identity_session_request(&identity,&request))return 2;
  response=0;session_result=ops->start(ops->context,&request,&jar,2);qq_secret_clear(&request,sizeof(request));
  for(i=0;!session_result&&i<200000;i++){
   if(network.transaction.response.head.status)session_status=(int)network.transaction.response.head.status;
   session_result=ops->poll(ops->context,&response);
  }
  if(session_result==1&&response){session_status=(int)response->head.status;session_valid=qq_identity_session_accept(&identity,response)==0;}
 }
 n=sony_snprintf(text,sizeof(text),"{\"native_result\":%d,\"http_status\":%d,\"transport_error\":%d,\"tls_error\":%d,\"response_bytes\":%u,\"qimei_valid\":%d,\"prior_tls_phase\":%d,\"prior_http_phase\":%d,\"sent_bytes\":%u,\"account_authenticated\":false}\n",rc,status,qimei_error,qimei_tls,(unsigned)reply_bytes,valid,previous_phase,previous_rx,(unsigned)previous_sent);
 qq_secret_clear(&ids,sizeof(ids));qq_secret_clear(installation,sizeof(installation));qq_identity_clear(&identity);ops->cancel(ops->context);qq_cookie_clear(&jar);
 if(n<=0||(size_t)n>=sizeof(text)||write(1,text,(size_t)n)!=n)return 74;
 n=sony_snprintf(text,sizeof(text),"{\"outer_json\":%u,\"inner_json\":%u,\"outer_code\":%llu,\"inner_code\":%llu,\"q16_bytes\":%u,\"q36_bytes\":%u}\n",outer_json,inner_json,(unsigned long long)outer_code,(unsigned long long)inner_code,q16_bytes,q36_bytes);
 if(n<=0||(size_t)n>=sizeof(text)||write(1,text,(size_t)n)!=n)return 74;
 n=sony_snprintf(text,sizeof(text),"{\"session_result\":%d,\"session_http_status\":%d,\"session_valid\":%d}\n",session_result,session_status,session_valid);
 if(n<=0||(size_t)n>=sizeof(text)||write(1,text,(size_t)n)!=n)return 74;
 return rc==1&&status==200&&valid&&session_valid?0:3;
#else
 if(rc==1&&response){status=(int)response->head.status;if(status==200&&response->body_bytes<=65536&&qq_image_qr(response->body,response->body_bytes,pixels,sizeof(pixels)/sizeof(*pixels),&w,&h)==0){valid_image=1;if(save(argv[2],response->body,response->body_bytes)||save(argv[3],pixels,(size_t)w*h*2))valid_image=0;}
  if(qq_cookie_header(&jar,"ssl.ptlogin2.qq.com","/ptqrlogin",network.clock.unix_seconds,cookie,sizeof(cookie))==0)has_qrsig=strstr(cookie,"qrsig=")!=0;
 }
 n=sony_snprintf(text,sizeof(text),"{\"native_result\":%d,\"http_status\":%d,\"transport_error\":%d,\"tls_error\":%d,\"valid_png\":%d,\"width\":%u,\"height\":%u,\"qrsig_present\":%d,\"account_authenticated\":false}\n",rc,status,network.error,network.tls_error,valid_image,w,h,has_qrsig);
 qq_secret_clear(cookie,sizeof(cookie));ops->cancel(ops->context);qq_cookie_clear(&jar);qq_secret_clear(pixels,sizeof(pixels));if(n<=0||(size_t)n>=sizeof(text)||write(1,text,(size_t)n)!=n)return 74;
 return rc==1&&status==200&&valid_image&&has_qrsig?0:3;
#endif
}
