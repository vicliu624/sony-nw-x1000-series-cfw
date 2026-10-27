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
#define task (job.task)
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
#include "../runtime/store/job_ui.h"
#include "../runtime/store/canvas.h"
static int dns,listener,peer=-1,seen,sent,closing,down,steps,requests;
static volatile int stop,server_stop;
static char request[2048];static unsigned used;
static const char *scenario;
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
  unsigned index=3;for(unsigned i=0;i<3;i++){char line[256];snprintf(line,sizeof line,"GET /apps/demo/0.1.0/%s HTTP/1.1\r\n",PLAN_PATHS[i]);if(!strncmp(request,line,strlen(line)))index=i;}
  assert(index<3);requests++;
  unsigned char response[256];int header=snprintf((char *)response,sizeof response,"HTTP/1.1 200 OK\r\nContent-Length: %u\r\n\r\n",PLAN_SIZES[index]);assert(header>0&&(unsigned)header+PLAN_SIZES[index]<sizeof response);memcpy(response+header,PLAN_BODIES[index],PLAN_SIZES[index]);
  if(!strcmp(scenario,"corrupt-resource")&&index==1)response[header]^=1;
  unsigned length=(unsigned)header+PLAN_SIZES[index];unsigned char *output=br_ssl_engine_sendapp_buf(&server_tls.eng,&n);assert(n>=length);memcpy(output,response,length);br_ssl_engine_sendapp_ack(&server_tls.eng,length);br_ssl_engine_flush(&server_tls.eng,0);sent=1;
 }else if(sent&&!closing&&(state&BR_SSL_SENDAPP)){br_ssl_engine_close(&server_tls.eng);closing=1;}
 (void)hb_tls_socket_deadline_step(&server_tls.eng,peer,&task.deadline,0,&server_stop);
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
int main(void){
 scenario=getenv("HB_TASK_SCENARIO");assert(scenario);hb_package_job_init(&job);hb_download_test_fault(0,0);
 struct sockaddr_in da,ta;dns=local_server(SOCK_DGRAM,&da);listener=local_server(SOCK_STREAM,&ta);assert(!listen(listener,4));
 struct in_addr nameserver;nameserver.s_addr=htonl(INADDR_LOOPBACK);struct ares_options options;memset(&options,0,sizeof options);options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=da.sin_port;options.tcp_port=da.sin_port;options.lookups="b";
 int mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS|ARES_OPT_SORTLIST;
 char base[160];assert(snprintf(base,sizeof base,"https://localhost:%u/apps/demo/0.1.0/",(unsigned)ntohs(ta.sin_port))<(int)sizeof base);
 assert(!hb_package_download_plan_init(&plan,"demo",base,PLAN_MF,sizeof PLAN_MF,PLAN_IX,sizeof PLAN_IX));
 assert(!hb_package_job_begin(&job,&plan,getenv("HB_TASK_CACHE"),getenv("HB_TASK_PACKAGES"),getenv("HB_TASK_APPS"),TAs,TAs_NUM,4096,5000,&stop,&options,mask));
 struct hb_store_canvas c;struct hb_store_painter p;assert(!hb_store_canvas_init(&c,pixels,240*432,&p));struct hb_store_ui_io io={0,next,present};
 int result=hb_job_ui_run(&job,&p,&io);
 if(!strcmp(scenario,"present-fail")){assert(result==-2&&job.state==HB_JOB_FAILED&&task.fd==-1&&!task.dns.channel&&task.connection.fd==-1);assert(!hb_package_job_discard(&job));}
 else {assert(!result&&job.state==HB_JOB_EMPTY);if(!strcmp(scenario,"complete"))assert(requests==3);}
 assert(!stop);if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;
}
