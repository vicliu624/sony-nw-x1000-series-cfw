#define _XOPEN_SOURCE 700
#include "../../runtime/apps/qqmusic/qqmusic_network.h"
#include <assert.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#ifdef QQ_NETWORK_FILE_FIXTURE
#define main volume_fixture_main
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_download.h"
static struct qq_download_file download;static struct qq_volume user_volume;static struct qq_storage_plan file_plan;static struct qq_response_sink file_sink;static volatile int file_stop;
static char contents[4096],workspace[4096],nested[4096];
static void file_open(const char *directory,int mode){uint64_t required;base=directory;
 assert(snprintf(contents,sizeof(contents),"%s/contents",base)>0&&mkdir(contents,0700)==0);assert(snprintf(workspace,sizeof(workspace),"%s/work",contents)>0&&mkdir(workspace,0700)==0);path(nested,"nested");assert(mkdir(nested,0700)==0);
 memset(&file_plan,0,sizeof(file_plan));file_plan.source=1048576;file_plan.files[0]=1;file_plan.reserve=4096;qq_volume_init(&user_volume);active=allow_source=1;
 {struct qq_storage_policy policy={"/dev/mock-user","vfat"};assert(qq_volume_open(&user_volume,&policy,"/contents/work/nested",&file_plan,&required)==0);}
 qq_download_init(&download);assert(qq_download_begin(&download,&user_volume,&file_plan,"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","0123456789abcdef",mode==17?1024:1048576,&file_stop)==0);file_sink=qq_download_sink(&download);
}
static void file_close(int expected){
 if(expected){struct qq_stage_file retained;struct qq_source_file reader;unsigned char data[4096];uint64_t offset=0;unsigned i;
  assert(download.stage.state==QQ_STAGE_READY&&qq_download_abort(&download)==0&&download.stage.state==QQ_STAGE_READY);qq_stage_init(&retained);assert(qq_download_take(&download,&retained)==0&&download.stage.state==QQ_STAGE_EMPTY);
  qq_source_init(&reader);assert(qq_source_open(&reader,&user_volume,&file_plan,&retained,&file_stop)==0);
  while(offset<reader.bytes){unsigned count=(unsigned)(reader.bytes-offset);if(count>sizeof(data))count=sizeof(data);assert(qq_source_read_at(&reader,offset,data,count)==(int)count);for(i=0;i<count;i++)assert(data[i]==(unsigned char)((offset+i)%251));offset+=count;}
  assert(offset==1048576&&qq_source_close(&reader)==0&&qq_stage_discard(&retained)==0);
 }else assert(qq_download_abort(&download)==0&&download.stage.state==QQ_STAGE_ABORTED);
 assert(qq_volume_close(&user_volume)==0);active=allow_source=0;assert(rmdir(nested)==0&&rmdir(workspace)==0&&rmdir(contents)==0&&!forbid_writes);
}
#endif
extern int sony_fcntl(int,int,...) __asm__("fcntl");
static struct qq_network network;
static br_x509_decoder_context decoder;
static unsigned char der[8192],dn[1024];static size_t dn_bytes;
static void append_dn(void *unused,const void *data,size_t n){(void)unused;assert(n<=sizeof(dn)-dn_bytes);memcpy(dn+dn_bytes,data,n);dn_bytes+=n;}
static int material(void *unused,struct qq_runtime_material *out){(void)unused;(void)out;return -1;}
static int no_time(struct hb_tls_time *out){(void)out;return -1;}
static int no_seed(unsigned char out[48],volatile int *stop){(void)stop;memset(out,0,48);return -1;}
static int future_time(struct hb_tls_time *out){int rc=hb_tls_current_time(out);if(!rc){out->days+=2;out->unix_seconds+=172800;}return rc;}
static unsigned descriptors(void){unsigned count=0;int i;for(i=0;i<128;i++)if(sony_fcntl(i,F_GETFD,0)>=0)count++;return count;}
#ifdef QQ_NETWORK_MEDIA_FIXTURE
static uint64_t media_bytes;static unsigned media_aborts,media_finishes;static int media_mode;static struct hb_sha256 media_hash;
static int media_sink_write(void *p,const unsigned char *data,size_t n){size_t i;(void)p;assert(n&&n<=4096);if(media_mode==16&&media_bytes)return -1;for(i=0;i<n;i++)assert(data[i]==(unsigned char)((media_bytes+i)%251));hb_sha256_update(&media_hash,data,(unsigned)n);media_bytes+=n;
#ifdef QQ_NETWORK_FILE_FIXTURE
 return file_sink.write(file_sink.opaque,data,n);
#else
 return 0;
#endif
}
static int media_sink_finish(void *p,uint64_t bytes,const unsigned char digest[32]){unsigned char actual[32];(void)p;assert(bytes==1048576&&bytes==media_bytes);hb_sha256_final(&media_hash,actual);assert(!memcmp(actual,digest,32));
#ifdef QQ_NETWORK_FILE_FIXTURE
 if(file_sink.finish(file_sink.opaque,bytes,digest))return -1;
#endif
 media_finishes++;return 0;}
static void media_sink_abort(void *p){(void)p;media_aborts++;
#ifdef QQ_NETWORK_FILE_FIXTURE
 file_sink.abort(file_sink.opaque);
#endif
}
#endif
int main(int argc,char **argv,char **env) {
 struct qq_network_config config;struct ares_options options;struct in_addr nameserver;
 br_x509_trust_anchor anchor;
#ifndef QQ_NETWORK_MEDIA_FIXTURE
 struct qq_cookie_jar jar,before;struct qq_request request;struct qq_response *response=0;
#else
 struct qq_resource resource;struct qq_response_sink sink={0,media_sink_write,media_sink_finish,media_sink_abort};
#endif
 const struct qq_runtime_ops *ops;int cert,mode,rc,expected;
 unsigned port,dns_port,initial,i;unsigned long long end;ssize_t bytes;(void)env;
 assert(argc==5||argc==6);dns_port=(unsigned)strtoul(argv[1],0,10);port=(unsigned)strtoul(argv[2],0,10);mode=atoi(argv[4]);assert(port&&port<=65535&&dns_port&&dns_port<=65535);
 cert=open(argv[3],O_RDONLY);assert(cert>=0);bytes=read(cert,der,sizeof(der));assert(bytes>0&&(size_t)bytes<sizeof(der));assert(close(cert)==0);
 br_x509_decoder_init(&decoder,append_dn,0);br_x509_decoder_push(&decoder,der,(size_t)bytes);assert(!br_x509_decoder_last_error(&decoder)&&br_x509_decoder_get_pkey(&decoder));
 memset(&anchor,0,sizeof(anchor));anchor.dn.data=dn;anchor.dn.len=dn_bytes;anchor.flags=BR_X509_TA_CA;anchor.pkey=*br_x509_decoder_get_pkey(&decoder);
 memset(&options,0,sizeof(options));nameserver.s_addr=htonl(INADDR_LOOPBACK);
 options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;
 options.servers=&nameserver;options.nservers=1;options.udp_port=htons((unsigned short)dns_port);options.tcp_port=options.udp_port;options.lookups="b";
 memset(&config,0,sizeof(config));config.anchors=&anchor;config.anchor_count=1;config.port=port;config.timeout_ms=5000;config.poll_ms=5;
 config.dns_options=&options;config.dns_mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS;
 if(mode==2)config.time=no_time;
 if(mode==3)config.seed=no_seed;
 if(mode==9)config.timeout_ms=100;
 if(mode==10)config.timeout_ms=300;
 if(mode==12)config.anchor_count=0;
 if(mode==15)config.time=future_time;
 initial=descriptors();rc=qq_network_init(&network,&config,0,material,0);
 if(mode==12){assert(rc<0&&descriptors()==initial);return 0;}assert(rc==0);
 ops=qq_network_operations(&network);assert(ops);
#ifdef QQ_NETWORK_FILE_FIXTURE
 assert(argc==6);file_open(argv[5],mode);
#endif
#ifdef QQ_NETWORK_MEDIA_FIXTURE
 memset(&resource,0,sizeof(resource));strcpy(resource.url,mode==11?"https://unapproved.invalid/song":"https://isure.stream.qqmusic.qq.com/M500MEDIA01.mp3?vkey=synthetic");
 strcpy(resource.ekey,"must-not-enter-transport");media_mode=mode;hb_sha256_init(&media_hash);
 rc=qq_network_media_begin(&network,&resource,mode==17?1024:1048576,mode==9||mode==10?1000:15000,sink);qq_resource_clear(&resource);end=network.deadline.end;
#else
 qq_cookie_clear(&jar);before=jar;assert(qq_build_authorize(&request,"o00123456","synthetic","random-state","synthetic-ui",100000)==0);
 if(mode==11)request.host="unapproved.invalid";
 rc=ops->start(ops->context,&request,&jar,1);qq_secret_clear(&request,sizeof(request));end=network.deadline.end;
#endif
 if(mode==4&&rc==0){ops->cancel(ops->context);rc=-1;}
 for(i=0;rc==0&&i<200000;i++) {
  if(mode==5&&network.phase==QQ_NET_TLS){ops->cancel(ops->context);rc=-1;break;}
#ifdef QQ_NETWORK_MEDIA_FIXTURE
  rc=qq_network_media_step(&network);
#else
  rc=ops->poll(ops->context,&response);
#endif
  assert(network.deadline.end==end);
 }
 assert(rc!=0);expected=mode==0||mode==1||mode==14;
#ifdef QQ_NETWORK_MEDIA_FIXTURE
 if(expected)assert(rc==1&&media_bytes==1048576&&media_finishes==1&&!media_aborts);
 else assert(rc<0&&!media_finishes&&media_aborts==(mode==11?0u:1u));
#else
 if(expected){assert(rc==1&&response&&response->phase==QQ_RX_DONE&&response->body_bytes==5&&!memcmp(response->body,"hello",5));assert(memcmp(&jar,&before,sizeof(jar)));}
 else {assert(rc<0&&!memcmp(&jar,&before,sizeof(jar)));for(i=0;i<sizeof(network.body);i++)assert(network.body[i]==0);}
#endif
 if(mode==7)assert(network.tls_error==BR_ERR_X509_BAD_SERVER_NAME);
 if(mode==8)assert(network.tls_error==BR_ERR_X509_NOT_TRUSTED);
 if(mode==15)assert(network.tls_error==BR_ERR_X509_EXPIRED);
 if(mode==14)assert(network.address==1);
 ops->cancel(ops->context);assert(network.fd==-1&&!network.dns.channel&&network.connection.fd==-1);
#ifdef QQ_NETWORK_FILE_FIXTURE
 file_close(expected);
#endif
 assert(!network.request.body[0]&&!network.transaction.wire[0]&&descriptors()==initial);
 for(i=0;i<sizeof(network.body);i++)assert(network.body[i]==0);
#ifdef QQ_NETWORK_MEDIA_FIXTURE
 assert(media_aborts==(expected||mode==11?0u:1u)&&!network.media_url[0]&&!network.media_sink_active);
#endif
 return 0;
}
