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
#ifdef HB_PLAN_TASKS
#include "../runtime/store/download_plan.h"
#include "package_task_fixture.h"
static struct hb_package_download_plan plan;
#endif
#ifdef HB_PACKAGE_ASSEMBLE
#include "../runtime/store/package_assemble.h"
#include "../runtime/store/install_posix.h"
static struct hb_package_download_plan assembly_plan;
static struct hb_package_assembly assembly;
static struct hb_bundle assembly_workspace;
static volatile int assembly_stop;
#endif
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern void hb_download_test_fault(int,int);
static struct hb_download_task task;
static br_ssl_server_context server_tls;
static unsigned char server_buffer[BR_SSL_BUFSIZE_BIDI];
#ifndef HB_PLAN_TASKS
static const unsigned char digest[32]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
#endif
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
static void erased(const void *pointer,unsigned bytes){const unsigned char *p=pointer;for(unsigned i=0;i<bytes;i++)assert(!p[i]);}
int main(void){
 hb_download_task_init(&task);
#ifdef HB_PLAN_TASKS
 for(unsigned file_index=0;file_index<3;file_index++){
  const int mode=0;
#ifdef HB_PACKAGE_ASSEMBLE
  const char *scenario=getenv("HB_TASK_SCENARIO");
  int corrupt_resource=scenario&&!strcmp(scenario,"corrupt-resource")&&file_index==1;
#endif
#else
 for(int mode=0;mode<9;mode++){
#endif
  hb_download_test_fault(0,0);struct sockaddr_in dns_address,tcp_address;
  int dns=local_server(SOCK_DGRAM,&dns_address),listener=local_server(SOCK_STREAM,&tcp_address);assert(!listen(listener,4));
  struct in_addr nameserver;nameserver.s_addr=htonl(INADDR_LOOPBACK);struct ares_options options;memset(&options,0,sizeof options);
  options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=dns_address.sin_port;options.tcp_port=dns_address.sin_port;options.lookups="b";
  int mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS|ARES_OPT_SORTLIST;
  unsigned char seed[48];for(unsigned i=0;i<48;i++)seed[i]=(unsigned char)(i+17);
  br_ssl_server_init_full_rsa(&server_tls,CHAIN,CHAIN_LEN,&RSA);br_ssl_engine_set_versions(&server_tls.eng,BR_TLS12,BR_TLS12);br_ssl_engine_set_buffer(&server_tls.eng,server_buffer,sizeof server_buffer,1);br_ssl_engine_inject_entropy(&server_tls.eng,seed,sizeof seed);assert(br_ssl_server_reset(&server_tls));
  char url[128],host_line[64];assert(snprintf(url,sizeof url,"https://localhost:%u/fixture",(unsigned)ntohs(tcp_address.sin_port))<(int)sizeof url);assert(snprintf(host_line,sizeof host_line,"\r\nHost: localhost:%u\r\n",(unsigned)ntohs(tcp_address.sin_port))<(int)sizeof host_line);
  volatile int stop=mode==7;
#ifdef HB_PLAN_TASKS
  char base[160],request_line[256];assert(snprintf(base,sizeof base,"https://localhost:%u/apps/demo/0.1.0/",(unsigned)ntohs(tcp_address.sin_port))<(int)sizeof base);
  assert(!hb_package_download_plan_init(&plan,"demo",base,PLAN_MF,sizeof PLAN_MF,PLAN_IX,sizeof PLAN_IX));
#ifdef HB_PACKAGE_ASSEMBLE
  if(!file_index){assembly_plan=plan;hb_package_assembly_init(&assembly);assert(!hb_package_assembly_begin(&assembly,getenv("HB_TASK_PACKAGES"),&assembly_plan,4096,&assembly_stop));}
#endif
  assert(snprintf(request_line,sizeof request_line,"GET /apps/demo/0.1.0/%s HTTP/1.1\r\n",PLAN_PATHS[file_index])<(int)sizeof request_line);
  int result=hb_download_task_begin_file(&task,&plan,file_index,TAs,TAs_NUM,getenv("HB_TASK_CACHE"),4096,5000,&stop,&options,mask);
#else
  int result=hb_download_task_begin(&task,url,mode==3?TAs+1:TAs,mode==3?1:TAs_NUM,getenv("HB_TASK_CACHE"),"task",3,digest,4096,mode==2?100:5000,&stop,&options,mask);
#endif
  if(mode==4)stop=1;
  if(mode==6)hb_download_test_fault(4,1);
  unsigned long long end=task.deadline.end;int answered=0,peer=-1,seen=0,sent=0,closing=0;char request[2048];unsigned used=0;volatile int peer_stop=0;
  for(unsigned tick=0;!result&&tick<200000;tick++){
   result=hb_download_task_step(&task,mode==2?1:0);assert(task.deadline.end==end);if(result)break;
   if(!answered)answered=dns_reply(dns,mode);
   if(peer<0){struct sockaddr_in remote;socklen_t size=sizeof remote;peer=accept(listener,(struct sockaddr *)&remote,&size);if(peer>=0)assert(remote.sin_addr.s_addr==htonl(INADDR_LOOPBACK));else assert(errno==EAGAIN||errno==EWOULDBLOCK);}
   if(peer>=0){
    unsigned state=br_ssl_engine_current_state(&server_tls.eng);size_t n;
    if(state&BR_SSL_RECVAPP){unsigned char *input=br_ssl_engine_recvapp_buf(&server_tls.eng,&n);assert(n<sizeof request-used);memcpy(request+used,input,n);used+=(unsigned)n;request[used]=0;br_ssl_engine_recvapp_ack(&server_tls.eng,n);if(strstr(request,"\r\n\r\n")){
#ifdef HB_PLAN_TASKS
     assert(!strncmp(request,request_line,strlen(request_line))&&strstr(request,host_line));
#else
     assert(!strncmp(request,"GET /fixture HTTP/1.1\r\n",sizeof("GET /fixture HTTP/1.1\r\n")-1)&&strstr(request,host_line));
#endif
     seen=1;}}
    state=br_ssl_engine_current_state(&server_tls.eng);
    if(seen&&!sent&&(state&BR_SSL_SENDAPP)){
#ifdef HB_PLAN_TASKS
     unsigned char response[256];int header=snprintf((char *)response,sizeof response,"HTTP/1.1 200 OK\r\nContent-Length: %u\r\n\r\n",PLAN_SIZES[file_index]);assert(header>0&&(unsigned)header+PLAN_SIZES[file_index]<sizeof response);memcpy(response+header,PLAN_BODIES[file_index],PLAN_SIZES[file_index]);unsigned length=(unsigned)header+PLAN_SIZES[file_index];
#ifdef HB_PACKAGE_ASSEMBLE
     if(corrupt_resource){assert(PLAN_SIZES[file_index]);response[header]^=1;}
#endif
#else
     const char *response=mode==5?"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabd":"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc";unsigned length=(unsigned)strlen(response);
#endif
     unsigned char *out=br_ssl_engine_sendapp_buf(&server_tls.eng,&n);assert(n>=length);memcpy(out,response,length);br_ssl_engine_sendapp_ack(&server_tls.eng,length);br_ssl_engine_flush(&server_tls.eng,0);sent=1;}
    else if(sent&&!closing&&(state&BR_SSL_SENDAPP)){br_ssl_engine_close(&server_tls.eng);closing=1;}
    (void)hb_tls_socket_deadline_step(&server_tls.eng,peer,&task.deadline,0,&peer_stop);
   }
  }
  int expected=mode==1?HB_DNS_LOOKUP:mode==2?HB_NET_DEADLINE:mode==3?HB_HTTPS_TLS:mode==4||mode==7?HB_NET_CANCELLED:mode==5?HB_DOWNLOAD_HASH:mode==6?HB_FETCH_RETAINED:1;
#ifdef HB_PACKAGE_ASSEMBLE
  if(corrupt_resource)expected=HB_DOWNLOAD_HASH;
#endif
  assert(result==expected&&task.fd==-1&&!task.dns.channel&&task.connection.fd==-1);
  if(mode==1||mode==2)assert(answered==1);
  erased(&task.client,sizeof task.client);erased(task.buffer,sizeof task.buffer);
  if(result==1){assert(task.phase==HB_NET_DONE&&task.file.state==HB_FETCH_READY);if(mode==8)assert(task.address_index==1&&task.address_count==2);int fd=open(task.file.path,O_RDONLY);
#ifdef HB_PLAN_TASKS
   unsigned char data[128];assert(fd>=0&&PLAN_SIZES[file_index]<sizeof data&&read(fd,data,PLAN_SIZES[file_index]+1)==(ssize_t)PLAN_SIZES[file_index]&&!memcmp(data,PLAN_BODIES[file_index],PLAN_SIZES[file_index])&&!close(fd));
#else
   char data[4];assert(fd>=0&&read(fd,data,4)==3&&!memcmp(data,"abc",3)&&!close(fd));
#endif
  }
  else{assert(task.phase==HB_NET_FAILED&&task.file.state!=HB_FETCH_READY&&hb_download_task_step(&task,0)==result);if(mode==3)assert(task.tls_error==BR_ERR_X509_NOT_TRUSTED&&!seen);}
#ifdef HB_PACKAGE_ASSEMBLE
  if(corrupt_resource){
   assert(result==HB_DOWNLOAD_HASH&&assembly.added==1&&assembly.state==HB_ASSEMBLE_OPEN);
   assert(hb_package_assembly_finish(&assembly,&assembly_workspace)==HB_ASSEMBLE_INCOMPLETE);
   stop=0;assert(!hb_download_task_discard(&task));
   if(peer>=0)assert(!close(peer));
   assert(!close(listener)&&!close(dns));return 0;
  }
  assert(result==1&&!hb_package_assembly_add(&assembly,file_index,&task.file));
#endif
  stop=0;hb_download_test_fault(0,0);
  if(mode==6){assert(task.file.state==HB_FETCH_REVIEW&&task.cleanup_pending);assert(!hb_download_file_recheck(&task.file)&&task.phase==HB_NET_FAILED&&hb_download_task_step(&task,0)==HB_FETCH_RETAINED);}
  assert(!hb_download_task_discard(&task)&&task.phase==HB_NET_EMPTY&&!task.file.owns);
  if(peer>=0)assert(!close(peer));
  assert(!close(listener)&&!close(dns));
 }
#ifdef HB_PACKAGE_ASSEMBLE
 assert(!hb_package_assembly_finish(&assembly,&assembly_workspace)&&assembly.state==HB_ASSEMBLE_READY);
 assert(!hb_store_install_local_expected(getenv("HB_TASK_APPS"),assembly.folder,"demo",4096,&assembly_stop,assembly_plan.identity));
#endif
#ifdef HB_PLAN_TASKS
 static const char message[]="planned app/binary-resource/empty downloads and task reuse passed\n";
#else
 static const char message[]="owned DNS/connect/TLS/HTTP/cache task: nine local cases and workspace reuse passed\n";
#endif
 return write(1,message,sizeof message-1)==(long)(sizeof message-1)?0:1;
}
