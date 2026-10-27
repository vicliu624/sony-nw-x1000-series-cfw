/* PC test harness only: real native network/download modules, local DNS/TLS.
 * Never included in production sources or supplied as an application profile. */
#include "../../runtime/apps/qqmusic/qqmusic_network.h"
#include "../../runtime/apps/qqmusic/qqmusic_download.h"
#include <arpa/inet.h>
static struct qq_network transfer_network;
static br_x509_decoder_context transfer_decoder;
static unsigned char transfer_der[8192],transfer_dn[2048];static size_t transfer_dn_bytes;
static void transfer_dn_append(void *unused,const void *p,size_t n){(void)unused;assert(n<=sizeof(transfer_dn)-transfer_dn_bytes);memcpy(transfer_dn+transfer_dn_bytes,p,n);transfer_dn_bytes+=n;}
static int transfer_material(void *unused,struct qq_runtime_material *out){(void)unused;(void)out;assert(0);return -1;}
static void transfer_source(struct qq_volume *volume,const struct qq_storage_plan *plan,struct qq_stage_file *source,const char *identity,const char *nonce,uint64_t maximum,volatile int *stop,char **arguments){
 struct qq_download_file download;struct qq_network_config config;struct ares_options options;struct in_addr nameserver;struct qq_resource resource;br_x509_trust_anchor anchor;
 int fd,rc;ssize_t n;unsigned i;unsigned dns_port=(unsigned)strtoul(arguments[0],0,10),tls_port=(unsigned)strtoul(arguments[1],0,10);
 assert(dns_port&&dns_port<=65535&&tls_port&&tls_port<=65535);
 fd=open(arguments[2],O_RDONLY);assert(fd>=0);n=sony_read(fd,transfer_der,sizeof(transfer_der));assert(n>0&&(size_t)n<sizeof(transfer_der)&&close(fd)==0);
 br_x509_decoder_init(&transfer_decoder,transfer_dn_append,0);br_x509_decoder_push(&transfer_decoder,transfer_der,(size_t)n);assert(!br_x509_decoder_last_error(&transfer_decoder)&&br_x509_decoder_get_pkey(&transfer_decoder));
 memset(&anchor,0,sizeof(anchor));anchor.dn.data=transfer_dn;anchor.dn.len=transfer_dn_bytes;anchor.flags=BR_X509_TA_CA;anchor.pkey=*br_x509_decoder_get_pkey(&transfer_decoder);
 memset(&options,0,sizeof(options));nameserver.s_addr=htonl(INADDR_LOOPBACK);options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=htons((unsigned short)dns_port);options.tcp_port=options.udp_port;options.lookups="b";
 memset(&config,0,sizeof(config));config.anchors=&anchor;config.anchor_count=1;config.port=tls_port;config.timeout_ms=5000;config.poll_ms=5;config.dns_options=&options;config.dns_mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS;
 assert(qq_network_init(&transfer_network,&config,0,transfer_material,0)==0);qq_download_init(&download);allow_source=1;
 assert(qq_download_begin(&download,volume,plan,identity,nonce,maximum,stop)==0);
 memset(&resource,0,sizeof(resource));strcpy(resource.url,"https://isure.stream.qqmusic.qq.com/O6M0MEDIA01.mgg?vkey=synthetic");
 rc=qq_network_media_begin(&transfer_network,&resource,(size_t)maximum,20000,qq_download_sink(&download));qq_resource_clear(&resource);
 for(i=0;!rc&&i<200000;i++)rc=qq_network_media_step(&transfer_network);
 assert(rc==1&&download.stage.state==QQ_STAGE_READY);qq_network_cancel(&transfer_network);assert(download.stage.state==QQ_STAGE_READY&&qq_download_abort(&download)==0);
 assert(qq_download_take(&download,source)==0);allow_source=0;
 assert(!transfer_network.media_url[0]&&!transfer_network.transaction.wire[0]);
}
