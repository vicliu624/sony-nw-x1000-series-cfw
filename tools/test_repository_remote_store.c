#define _GNU_SOURCE
#include "../runtime/store/download_task.h"
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include "chain-rsa.h"
#include "key-rsa.h"
#include "../runtime/store/download_plan.h"
#include "package_task_fixture.h"
#include "../runtime/store/package_job.h"
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern int sony_setsockopt(int,int,int,const void *,socklen_t) __asm__("setsockopt");
extern void hb_download_test_fault(int,int);
extern void hb_repository_record_exit(int);
static br_ssl_server_context server_tls;
static unsigned char server_buffer[BR_SSL_BUFSIZE_BIDI];
static int local_server(int type,struct sockaddr_in *address){
 int fd=socket(AF_INET,type,0);assert(fd>=0);memset(address,0,sizeof *address);address->sin_family=AF_INET;address->sin_addr.s_addr=htonl(INADDR_LOOPBACK);
 if(type==SOCK_STREAM){int yes=1;assert(!sony_setsockopt(fd,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof yes));const char *fixed=getenv("HB_META_TEST_PORT");if(fixed){unsigned port=0;for(;*fixed;fixed++){assert(*fixed>='0'&&*fixed<='9'&&port<=6553);port=port*10+(unsigned)(*fixed-'0');assert(port<=65535);}assert(port);address->sin_port=htons((unsigned short)port);}}
 assert(!bind(fd,(const struct sockaddr *)address,sizeof *address));socklen_t size=sizeof *address;assert(!getsockname(fd,(struct sockaddr *)address,&size));
 int flags=sony_fcntl(fd,F_GETFL,0);assert(flags>=0&&!sony_fcntl(fd,F_SETFL,flags|O_NONBLOCK));return fd;
}
static int dns_reply(int fd,int mode){
 unsigned char packet[512],response[512];struct sockaddr_in peer;socklen_t size=sizeof peer;
 ssize_t n=recvfrom(fd,packet,sizeof packet,MSG_DONTWAIT,(struct sockaddr *)&peer,&size);
 if(n<0){assert(errno==EAGAIN||errno==EWOULDBLOCK);return 0;}
 assert(n>=17&&peer.sin_addr.s_addr==htonl(INADDR_LOOPBACK));unsigned pos=12,length=0;char name[254];
 while(pos<(unsigned)n&&packet[pos]){unsigned count=packet[pos++];assert(count<=63&&pos+count<(unsigned)n&&length+count+1<sizeof name);if(length)name[length++]='.';memcpy(name+length,packet+pos,count);length+=count;pos+=count;}
 name[length]=0;assert(!strcmp(name,"localhost"));pos++;assert(pos+4<=(unsigned)n&&packet[pos+1]==1&&packet[pos+3]==1);pos+=4;
 if(mode==2)return 1;
 memcpy(response,packet,pos);response[2]=0x81;response[3]=mode==1?0x83:0x80;
 unsigned answers=mode==1?0:mode==8?2:1;response[4]=0;response[5]=1;response[6]=0;response[7]=(unsigned char)answers;for(unsigned i=8;i<12;i++)response[i]=0;
 for(unsigned i=0;i<answers;i++){unsigned char record[16]={0xc0,0x0c,0,1,0,1,0,0,0,30,0,4,127,0,0,(unsigned char)(mode==8?(i?1:2):1)};memcpy(response+pos,record,16);pos+=16;}
 assert(sendto(fd,response,pos,0,(const struct sockaddr *)&peer,sizeof peer)==(ssize_t)pos);return 1;
}
#include "../runtime/store/metadata_fetch.h"
#include "../runtime/store/remote_catalog.h"
#include "../runtime/store/remote_list.h"
#include "../runtime/store/remote_store.h"
#include "../runtime/store/repository.h"
#include "../runtime/store/job_ui.h"
#include "../runtime/store/canvas.h"
static int dns,listener,peer=-1,seen,sent,closing,down,steps,requests;
static volatile int stop,server_stop;
static char request[2048];static unsigned used;
static const char *scenario;static int recovery_seen,metadata_recovery_seen;
static struct hb_transfer_deadline *active_deadline;
static const unsigned char *served[6];static unsigned sizes[6];
static const char *paths[6]={"/apps/demo/0.1.0/app","/apps/demo/0.1.0/assets/icon.bin","/apps/demo/0.1.0/empty.dat","/catalog.txt","/apps/demo/0.1.0/app.ini","/apps/demo/0.1.0/files.sha256"};
static char listing[2048];static struct hb_remote_store store;static struct hb_repository repository;
static void hash_bytes(const unsigned char *data,unsigned bytes,unsigned char out[32]){struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,data,bytes);hb_sha256_final(&h,out);}
static void hex_digest(const unsigned char digest[32],char out[65]){const char *hex="0123456789abcdef";for(unsigned i=0;i<32;i++){out[i*2]=hex[digest[i]>>4];out[i*2+1]=hex[digest[i]&15];}out[64]=0;}

static unsigned short pixels[240*432];
static void init_peer(void){
 unsigned char seed[48];for(unsigned i=0;i<48;i++)seed[i]=(unsigned char)(i+17);
 br_ssl_server_init_full_rsa(&server_tls,CHAIN,CHAIN_LEN,&RSA);br_ssl_engine_set_versions(&server_tls.eng,BR_TLS12,BR_TLS12);br_ssl_engine_set_buffer(&server_tls.eng,server_buffer,sizeof server_buffer,1);br_ssl_engine_inject_entropy(&server_tls.eng,seed,sizeof seed);assert(br_ssl_server_reset(&server_tls));
 seen=sent=closing=0;used=0;
}
static void pump(void){
 (void)dns_reply(dns,0);
 if(peer<0){struct sockaddr_in address;socklen_t size=sizeof address;peer=accept(listener,(struct sockaddr *)&address,&size);if(peer<0){assert(errno==EAGAIN||errno==EWOULDBLOCK);return;}assert(address.sin_addr.s_addr==htonl(INADDR_LOOPBACK));init_peer();}
 unsigned state=br_ssl_engine_current_state(&server_tls.eng);size_t n;
 if(state&BR_SSL_RECVAPP){unsigned char *input=br_ssl_engine_recvapp_buf(&server_tls.eng,&n);assert(n<sizeof request-used);memcpy(request+used,input,n);used+=(unsigned)n;request[used]=0;br_ssl_engine_recvapp_ack(&server_tls.eng,n);if(strstr(request,"\r\n\r\n"))seen=1;}
 state=br_ssl_engine_current_state(&server_tls.eng);
 if(seen&&!sent&&(state&BR_SSL_SENDAPP)){
  unsigned index=6;for(unsigned i=0;i<6;i++){char line[256];snprintf(line,sizeof line,"GET %s HTTP/1.1\r\n",paths[i]);if(!strncmp(request,line,strlen(line)))index=i;}
  assert(index<6);requests++;
  unsigned char response[4096];int header=snprintf((char *)response,sizeof response,"HTTP/1.1 200 OK\r\nContent-Length: %u\r\n\r\n",sizes[index]);assert(header>0&&(unsigned)header+sizes[index]<sizeof response);memcpy(response+header,served[index],sizes[index]);
  if((!strcmp(scenario,"corrupt-resource")&&index==1)||(!strcmp(scenario,"metadata-hash")&&index==4))response[header]^=1;
  unsigned length=(unsigned)header+sizes[index];unsigned char *output=br_ssl_engine_sendapp_buf(&server_tls.eng,&n);assert(n>=length);memcpy(output,response,length);br_ssl_engine_sendapp_ack(&server_tls.eng,length);br_ssl_engine_flush(&server_tls.eng,0);sent=1;
 }else if(sent&&!closing&&(state&BR_SSL_SENDAPP)){br_ssl_engine_close(&server_tls.eng);closing=1;}
 (void)hb_tls_socket_deadline_step(&server_tls.eng,peer,active_deadline,0,&server_stop);
 if(br_ssl_engine_current_state(&server_tls.eng)==BR_SSL_CLOSED){assert(!close(peer));peer=-1;}
}
static int present(void *ctx){
 (void)ctx;static int captured;
 const char *preview=getenv("HB_UI_PREVIEW");
 if(preview&&!captured&&store.job.state==HB_JOB_READY){
  FILE *file=fopen(preview,"wb");assert(file);static const char header[]="P6\n240 432\n255\n";assert(fwrite(header,1,sizeof header-1,file)==sizeof header-1);
  for(unsigned i=0;i<240*432;i++){unsigned short c=pixels[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};assert(fwrite(rgb,1,3,file)==3);}
  assert(!fclose(file));captured=1;
 }
 return (!strcmp(scenario,"present-fail")&&store.job.state==HB_JOB_FETCH)||(!strcmp(scenario,"meta-retry-present-fail")&&metadata_recovery_seen&&store.metadata.state==HB_METADATA_FETCHING)?-1:0;
}
static int next(void *ctx,unsigned char packet[11]){
 (void)ctx;assert(++steps<200000);int x=180,y=404;
 if(!strcmp(scenario,"crash-record")&&store.stage==HB_REMOTE_PACKAGE&&store.job.state==HB_JOB_OPEN)hb_repository_record_exit(1);
 if(!strcmp(scenario,"crash-metadata")&&store.stage==HB_REMOTE_CATALOG&&store.metadata.state==HB_METADATA_FETCHING&&store.metadata.task.phase==HB_NET_TRANSFER)hb_repository_record_exit(1);
 if(!strcmp(scenario,"crash-payload")&&store.stage==HB_REMOTE_PACKAGE&&store.job.index==1&&store.job.state==HB_JOB_FETCH)_exit(77);
 if(store.stage==HB_REMOTE_LIST){x=20;y=!strcmp(scenario,"list-back")?404:70;}
 else {
  active_deadline=store.stage==HB_REMOTE_PACKAGE?&store.job.task.deadline:&store.metadata.task.deadline;pump();
  int tap=store.stage==HB_REMOTE_PACKAGE&&(store.job.state==HB_JOB_READY||store.job.state==HB_JOB_INSTALLED||store.job.state==HB_JOB_FAILED||store.job.state==HB_JOB_RECOVERY);
  if(store.job.state==HB_JOB_RECOVERY){recovery_seen=1;if(!strcmp(scenario,"recover-back"))x=20;}
  if(store.job.state==HB_JOB_FAILED&&store.job.unowned_conflict)x=20;
  if(!strcmp(scenario,"cancel-second")&&store.stage==HB_REMOTE_PACKAGE&&store.job.index==1)tap=1;
  if(!strcmp(scenario,"metadata-cancel")&&store.stage==HB_REMOTE_CATALOG)tap=1;
  if(store.metadata.state==HB_METADATA_RECOVERY){metadata_recovery_seen=1;assert(!store.metadata.bytes);for(unsigned i=0;i<sizeof store.metadata.data;i++)assert(!store.metadata.data[i]);tap=1;if(!strcmp(scenario,"meta-back"))x=20;}
  if(!tap)return 0;
 }
 memset(packet,0,11);packet[1]=(unsigned char)!down;down=!down;unsigned rx=((unsigned)x*2929+239)/240,ry=((431-(unsigned)y)*5281+431)/432;
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
int main(void){
 scenario=getenv("HB_TASK_SCENARIO");assert(scenario);hb_remote_store_init(&store);hb_download_test_fault(0,0);hb_repository_record_exit(0);
 if(!strcmp(scenario,"seed-record")){assert(!hb_package_download_plan_init(&store.plan,"demo","https://example.test/demo/",PLAN_MF,sizeof PLAN_MF,PLAN_IX,sizeof PLAN_IX));assert(!hb_download_record_save(&store.job.record,getenv("HB_TASK_PACKAGES"),&store.plan,4096,&stop));return 0;}
 struct sockaddr_in da,ta;dns=local_server(SOCK_DGRAM,&da);listener=local_server(SOCK_STREAM,&ta);assert(!listen(listener,4));
 struct in_addr nameserver;nameserver.s_addr=htonl(INADDR_LOOPBACK);struct ares_options options;memset(&options,0,sizeof options);options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=da.sin_port;options.tcp_port=da.sin_port;options.lookups="b";
 int mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS|ARES_OPT_SORTLIST;
 char base[160];assert(snprintf(base,sizeof base,"https://localhost:%u/apps/demo/0.1.0/",(unsigned)ntohs(ta.sin_port))<(int)sizeof base);

 for(unsigned i=0;i<3;i++){served[i]=PLAN_BODIES[i];sizes[i]=PLAN_SIZES[i];assert(strstr(paths[i],PLAN_PATHS[i]));}
 served[4]=PLAN_MF;sizes[4]=sizeof PLAN_MF;served[5]=PLAN_IX;sizes[5]=sizeof PLAN_IX;
 unsigned char mf_hash[32],ix_hash[32];char mf_hex[65],ix_hex[65];hash_bytes(PLAN_MF,sizeof PLAN_MF,mf_hash);hash_bytes(PLAN_IX,sizeof PLAN_IX,ix_hash);hex_digest(mf_hash,mf_hex);hex_digest(ix_hash,ix_hex);
 int count=snprintf(listing,sizeof listing,"HBSTORE1\ndemo\t0.1.0\t%s\t%u\t%s\t%u\t%s\n",base,(unsigned)sizeof PLAN_MF,mf_hex,(unsigned)sizeof PLAN_IX,ix_hex);assert(count>0&&count<(int)sizeof listing);served[3]=(const unsigned char *)listing;sizes[3]=(unsigned)count;
 struct hb_store_canvas c;struct hb_store_painter p;assert(!hb_store_canvas_init(&c,pixels,240*432,&p));struct hb_store_ui_io io={0,next,present};
 char url[256];assert(snprintf(url,sizeof url,"https://localhost:%u/catalog.txt",(unsigned)ntohs(ta.sin_port))<(int)sizeof url);unsigned char root_hash[32];hash_bytes(served[3],sizes[3],root_hash);
 char root_hex[65];hex_digest(root_hash,root_hex);const char *repository_dir=getenv("HB_TEST_REPOSITORY"),*ca_hex=getenv("HB_TEST_CA_HASH");assert(repository_dir&&ca_hex&&strlen(ca_hex)==64);
 char config_path[512],config_text[4096];assert(snprintf(config_path,sizeof config_path,"%s/repository.conf",repository_dir)<(int)sizeof config_path);
 int text_bytes=snprintf(config_text,sizeof config_text,"HBREPO1\ncatalog_url=%s\ncatalog_bytes=%u\ncatalog_sha256=%s\nca_sha256=%s\n",url,sizes[3],root_hex,ca_hex);assert(text_bytes>0&&text_bytes<(int)sizeof config_text);
 int config_fd=open(config_path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);assert(config_fd>=0&&write(config_fd,config_text,(unsigned)text_bytes)==text_bytes&&!close(config_fd));
 assert(!hb_repository_load(repository_dir,&stop,&repository)&&repository.valid);
 struct hb_remote_store_config config={.catalog_url=repository.spec.catalog_url,.catalog_bytes=repository.spec.catalog_bytes,.catalog_sha256=repository.spec.catalog_sha256,.cache=getenv("HB_TASK_CACHE"),.packages=getenv("HB_TASK_PACKAGES"),.apps=getenv("HB_TASK_APPS"),.running_id="store",.anchors=&repository.anchor,.anchor_count=1,.timeout_ms=5000,.reserve=4096,.stop=&stop,.options=&options,.option_mask=mask};
 int seed_item=!strncmp(scenario,"meta-",5)?3:!strncmp(scenario,"info-",5)?4:!strncmp(scenario,"index-",6)?5:-1;
 if(seed_item>=0){
  char selected_url[256];const char *cache_url=url;
  if(seed_item!=3){assert(snprintf(selected_url,sizeof selected_url,"%s%s",base,seed_item==4?"app.ini":"files.sha256")<(int)sizeof selected_url);cache_url=selected_url;}
  unsigned char selected_hash[32];hash_bytes(served[seed_item],sizes[seed_item],selected_hash);char key[33],path[512];assert(!hb_metadata_cache_key(cache_url,sizes[seed_item],selected_hash,key));assert(snprintf(path,sizeof path,"%s/.fetch-%s",getenv("HB_TASK_CACHE"),key)<(int)sizeof path);
  if(!strcmp(scenario,"meta-link")){char other[512];assert(snprintf(other,sizeof other,"%s/unrelated",getenv("HB_TASK_APPS"))<(int)sizeof other);assert(!symlink(other,path));}
  else if(access(path,F_OK)){
   unsigned char copy[4096];assert(sizes[seed_item]<sizeof copy);memcpy(copy,served[seed_item],sizes[seed_item]);unsigned amount=strstr(scenario,"-complete")||!strcmp(scenario,"meta-corrupt")?sizes[seed_item]:1;if(!strcmp(scenario,"meta-corrupt"))copy[0]^=1;
   int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);assert(fd>=0&&write(fd,copy,amount)==(ssize_t)amount&&!close(fd));
  }
 }
 int result=hb_remote_store_run(&store,&config,&p,&io);
 if(!strcmp(scenario,"meta-back")){assert(result==-1&&store.stage==HB_REMOTE_CATALOG&&store.metadata.state==HB_METADATA_RECOVERY&&metadata_recovery_seen&&requests==0);}
 else if(!strcmp(scenario,"meta-link")){assert(result==-2&&store.stage==HB_REMOTE_CATALOG&&!store.metadata.previous.valid&&!store.metadata.task.dns.channel&&store.job.state==HB_JOB_EMPTY);}
 else if(!strcmp(scenario,"meta-retry-present-fail")){assert(result==-2&&store.stage==HB_REMOTE_CATALOG&&metadata_recovery_seen&&store.metadata.task.fd==-1&&!store.metadata.task.dns.channel&&requests==0);}
 else if(!strcmp(scenario,"present-fail")){assert(result==-2&&store.stage==HB_REMOTE_PACKAGE&&store.job.task.fd==-1&&!store.job.task.dns.channel);}
 else if(!strcmp(scenario,"metadata-hash")){
  assert(result==-2&&store.error==HB_DOWNLOAD_HASH&&store.stage==HB_REMOTE_MANIFEST&&store.job.state==HB_JOB_EMPTY&&requests==2);
  assert(!store.metadata.bytes);for(unsigned i=0;i<sizeof store.metadata.data;i++)assert(!store.metadata.data[i]);
 }else if(!strcmp(scenario,"list-back"))assert(result==-1&&store.stage==HB_REMOTE_LIST&&requests==1);
 else if(!strcmp(scenario,"metadata-cancel"))assert(result==-1&&store.error==HB_NET_CANCELLED&&!store.metadata.task.dns.channel&&store.metadata.task.fd==-1);
 else {assert(!result&&store.stage==HB_REMOTE_FINISHED);if(!strcmp(scenario,"complete"))assert(requests==6);if(!strcmp(scenario,"resume-complete"))assert(requests==3);if(!strcmp(scenario,"recover-restart"))assert(requests==6&&recovery_seen);if(!strcmp(scenario,"meta-complete")||!strcmp(scenario,"info-complete")||!strcmp(scenario,"index-complete"))assert(requests==5&&!metadata_recovery_seen);if(!strcmp(scenario,"meta-retry")||!strcmp(scenario,"meta-corrupt")||!strcmp(scenario,"info-retry")||!strcmp(scenario,"index-retry"))assert(requests==6&&metadata_recovery_seen);if(!strcmp(scenario,"recover-back"))assert(requests==3&&recovery_seen&&store.job.state==HB_JOB_RECOVERY&&store.job.record.owns);}
 assert(hb_remote_store_run(&store,&config,&p,&io)==-2);if(strcmp(scenario,"recover-back")&&strcmp(scenario,"meta-back"))assert(!hb_remote_store_discard(&store)&&store.stage==HB_REMOTE_IDLE&&!store.begun);
 assert(!stop);if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;
}
