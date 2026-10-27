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
#include "fixture_ta.h"
#include "chain-rsa.h"
#include "key-rsa.h"
#include "../runtime/store/download_plan.h"
#include "package_task_fixture.h"
static struct hb_package_download_plan plan;
#include "../runtime/store/package_job.h"
static struct hb_package_job job;
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern void hb_download_test_fault(int,int);
static br_ssl_server_context server_tls;
static unsigned char server_buffer[BR_SSL_BUFSIZE_BIDI];
static int local_server(int type,struct sockaddr_in *address){
 int fd=socket(AF_INET,type,0);assert(fd>=0);memset(address,0,sizeof *address);address->sin_family=AF_INET;address->sin_addr.s_addr=htonl(INADDR_LOOPBACK);
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
#include "../runtime/store/job_ui.h"
#include "../runtime/store/canvas.h"
static int dns,listener,peer=-1,seen,sent,closing,down,steps,requests;
static volatile int stop,server_stop;
static char request[2048];static unsigned used;
static const char *scenario;
static struct hb_metadata_fetch metadata;
static struct hb_remote_catalog catalog;
static struct hb_transfer_deadline *active_deadline;
static const unsigned char *served[6];static unsigned sizes[6];
static const char *paths[6]={"/apps/demo/0.1.0/app","/apps/demo/0.1.0/assets/icon.bin","/apps/demo/0.1.0/empty.dat","/catalog.txt","/apps/demo/0.1.0/app.ini","/apps/demo/0.1.0/files.sha256"};
static char listing[2048];static unsigned char mf_copy[1024],ix_copy[HB_INVENTORY_TEXT_BYTES];
static unsigned mf_bytes,ix_bytes;static int selected;
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
 if(preview&&!captured&&job.state==HB_JOB_READY){
  FILE *file=fopen(preview,"wb");assert(file);static const char header[]="P6\n240 432\n255\n";assert(fwrite(header,1,sizeof header-1,file)==sizeof header-1);
  for(unsigned i=0;i<240*432;i++){unsigned short c=pixels[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};assert(fwrite(rgb,1,3,file)==3);}
  assert(!fclose(file));captured=1;
 }
 return !strcmp(scenario,"present-fail")&&job.state==HB_JOB_FETCH?-1:0;
}
static int next(void *ctx,unsigned char packet[11]){
 (void)ctx;assert(++steps<200000);pump();
 int tap=job.state==HB_JOB_READY||job.state==HB_JOB_INSTALLED||job.state==HB_JOB_FAILED;
 if(!strcmp(scenario,"cancel-second")&&job.index==1)tap=1;
 if(!tap)return 0;
 memset(packet,0,11);packet[1]=(unsigned char)!down;down=!down;unsigned x=180,y=404,rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
static int choose_next(void *ctx,unsigned char packet[11]){
 (void)ctx;static unsigned sample;assert(sample<2);memset(packet,0,11);packet[1]=(unsigned char)(sample++==0);
 unsigned x=20,y=!strcmp(scenario,"list-back")?404:70,rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
int main(void){
 scenario=getenv("HB_TASK_SCENARIO");assert(scenario);hb_package_job_init(&job);hb_download_test_fault(0,0);
 struct sockaddr_in da,ta;dns=local_server(SOCK_DGRAM,&da);listener=local_server(SOCK_STREAM,&ta);assert(!listen(listener,4));
 struct in_addr nameserver;nameserver.s_addr=htonl(INADDR_LOOPBACK);struct ares_options options;memset(&options,0,sizeof options);options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=da.sin_port;options.tcp_port=da.sin_port;options.lookups="b";
 int mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS|ARES_OPT_SORTLIST;
 char base[160];assert(snprintf(base,sizeof base,"https://localhost:%u/apps/demo/0.1.0/",(unsigned)ntohs(ta.sin_port))<(int)sizeof base);

 for(unsigned i=0;i<3;i++){served[i]=PLAN_BODIES[i];sizes[i]=PLAN_SIZES[i];assert(strstr(paths[i],PLAN_PATHS[i]));}
 served[4]=PLAN_MF;sizes[4]=sizeof PLAN_MF;served[5]=PLAN_IX;sizes[5]=sizeof PLAN_IX;
 unsigned char mf_hash[32],ix_hash[32];char mf_hex[65],ix_hex[65];hash_bytes(PLAN_MF,sizeof PLAN_MF,mf_hash);hash_bytes(PLAN_IX,sizeof PLAN_IX,ix_hash);hex_digest(mf_hash,mf_hex);hex_digest(ix_hash,ix_hex);
 int count=snprintf(listing,sizeof listing,"HBSTORE1\ndemo\t0.1.0\t%s\t%u\t%s\t%u\t%s\n",base,(unsigned)sizeof PLAN_MF,mf_hex,(unsigned)sizeof PLAN_IX,ix_hex);assert(count>0&&count<(int)sizeof listing);served[3]=(const unsigned char *)listing;sizes[3]=(unsigned)count;
 struct hb_store_canvas c;struct hb_store_painter p;assert(!hb_store_canvas_init(&c,pixels,240*432,&p));
 for(unsigned item=3;item<6;item++){
  char url[256];assert(snprintf(url,sizeof url,"https://localhost:%u%s",(unsigned)ntohs(ta.sin_port),paths[item])<(int)sizeof url);
  if(item>3)assert(snprintf(url,sizeof url,"%s%s",catalog.entries[selected].base_url,item==4?"app.ini":"files.sha256")<(int)sizeof url);
  unsigned char expected[32];unsigned expected_bytes;
  if(item==3){hash_bytes(served[3],sizes[3],expected);expected_bytes=sizes[3];} /* Pinned test repository root, not a production trust bootstrap. */
  else {assert(catalog.valid&&catalog.count==1);expected_bytes=item==4?catalog.entries[selected].manifest_bytes:catalog.entries[selected].index_bytes;memcpy(expected,item==4?catalog.entries[selected].manifest_sha256:catalog.entries[selected].index_sha256,32);}
  hb_metadata_fetch_init(&metadata);assert(!hb_metadata_fetch_begin(&metadata,url,expected_bytes,expected,TAs,TAs_NUM,getenv("HB_TASK_CACHE"),4096,5000,&stop,&options,mask));active_deadline=&metadata.task.deadline;
  int result=0;unsigned ticks=0;while(!result&&ticks++<200000){result=hb_metadata_fetch_step(&metadata,0);if(!result)pump();}
  if(!strcmp(scenario,"metadata-hash")&&item==4){
   assert(result==HB_DOWNLOAD_HASH&&metadata.state==HB_METADATA_FAILED&&!metadata.bytes&&job.state==HB_JOB_EMPTY&&requests==2);
   for(unsigned i=0;i<sizeof metadata.data;i++)assert(!metadata.data[i]);
   assert(!hb_metadata_fetch_discard(&metadata));if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;
  }
  assert(result==1&&ticks<200000&&metadata.state==HB_METADATA_READY);
  if(item==3){
   assert(!hb_remote_catalog_parse(metadata.data,metadata.bytes,&catalog));struct hb_store_ui_io choose={0,choose_next,present};selected=hb_remote_list_run(&catalog,"store",&p,&choose);
   if(selected<0){assert(!strcmp(scenario,"list-back")&&selected==-1&&requests==1);assert(!hb_metadata_fetch_discard(&metadata));if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;}
   assert((unsigned)selected<catalog.count&&!strcmp(catalog.entries[selected].id,"demo"));
  }
  else if(item==4){mf_bytes=metadata.bytes;memcpy(mf_copy,metadata.data,mf_bytes);}
  else {ix_bytes=metadata.bytes;memcpy(ix_copy,metadata.data,ix_bytes);}
  assert(!hb_metadata_fetch_discard(&metadata));
 }
 assert(!hb_remote_entry_plan(catalog.entries+selected,mf_copy,mf_bytes,ix_copy,ix_bytes,&plan));active_deadline=&job.task.deadline;

 assert(!hb_package_job_begin(&job,&plan,getenv("HB_TASK_CACHE"),getenv("HB_TASK_PACKAGES"),getenv("HB_TASK_APPS"),TAs,TAs_NUM,4096,5000,&stop,&options,mask));
 struct hb_store_ui_io io={0,next,present};
 int result=hb_job_ui_run(&job,&p,&io);
 if(!strcmp(scenario,"present-fail")){assert(result==-2&&job.state==HB_JOB_FAILED&&job.task.fd==-1&&!job.task.dns.channel&&job.task.connection.fd==-1);assert(!hb_package_job_discard(&job));}
 else {assert(!result&&job.state==HB_JOB_EMPTY);if(!strcmp(scenario,"complete"))assert(requests==6);}
 assert(!stop);if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;
}
