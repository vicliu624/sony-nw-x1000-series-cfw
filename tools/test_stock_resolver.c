#define _GNU_SOURCE
#include "../runtime/store/resolver.h"
#include <arpa/inet.h>
#include <unistd.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
static int reply(int fd,int mode){
 unsigned char packet[1024],response[1024];struct sockaddr_in peer;socklen_t size=sizeof peer;
 ssize_t n=recvfrom(fd,packet,sizeof packet,MSG_DONTWAIT,(struct sockaddr *)&peer,&size);
 if(n<0){assert(errno==EAGAIN||errno==EWOULDBLOCK);return 0;}
 assert(n>=17&&peer.sin_family==AF_INET&&peer.sin_addr.s_addr==htonl(INADDR_LOOPBACK));
 unsigned pos=12,used=0;char name[254];
 while(pos<(unsigned)n&&packet[pos]){
  unsigned length=packet[pos++];assert(length<=63&&pos+length<(unsigned)n&&used+length+1<sizeof name);
  if(used)name[used++]='.';
  memcpy(name+used,packet+pos,length);used+=length;pos+=length;
 }
 name[used]=0;assert(!strcmp(name,"fixture.invalid"));pos++;
 assert(pos+4<=(unsigned)n&&packet[pos]==0&&packet[pos+1]==1&&packet[pos+2]==0&&packet[pos+3]==1);pos+=4;
 if(mode==2)return 1;
 memcpy(response,packet,pos);response[2]=0x81;response[3]=mode==1?0x83:0x80;
 unsigned answers=mode==1?0:mode==5?9:mode==7?2:1;
 response[4]=0;response[5]=1;response[6]=0;response[7]=(unsigned char)answers;
 for(unsigned i=8;i<12;i++)response[i]=0;
 for(unsigned i=0;i<answers;i++){
  const unsigned char record[16]={0xc0,0x0c,0,1,0,1,0,0,0,30,0,4,127,0,0,(unsigned char)(i+1)};
  memcpy(response+pos,record,sizeof record);pos+=sizeof record;
 }
 assert(sendto(fd,response,pos,0,(const struct sockaddr *)&peer,sizeof peer)==(ssize_t)pos);return 1;
}
int main(void){
 for(int mode=0;mode<8;mode++){
  int server=socket(AF_INET,SOCK_DGRAM,0);assert(server>=0);
  struct sockaddr_in address;memset(&address,0,sizeof address);address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  assert(!bind(server,(const struct sockaddr *)&address,sizeof address));socklen_t size=sizeof address;
  assert(!getsockname(server,(struct sockaddr *)&address,&size)&&address.sin_addr.s_addr==htonl(INADDR_LOOPBACK));
  struct in_addr nameserver;nameserver.s_addr=htonl(INADDR_LOOPBACK);struct ares_options options;memset(&options,0,sizeof options);
  options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;
  options.servers=&nameserver;options.nservers=1;options.udp_port=address.sin_port;options.tcp_port=address.sin_port;options.lookups="b";
  int mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS;
  struct hb_transfer_deadline deadline;assert(!hb_transfer_deadline_init(&deadline,mode==4?0:mode==2?20:1000));
  struct hb_dns_query query;hb_dns_init(&query);volatile int stop=0;
  int result=hb_dns_begin(&query,mode==6?"bad\r\n.invalid":"fixture.invalid",443,&deadline,&stop,&options,mask);
  unsigned replies=0;
  if(mode==3){assert(!result);stop=1;result=hb_dns_step(&query,0);}
  else for(unsigned tick=0;!result&&tick<100000;tick++){
   result=hb_dns_step(&query,mode==2?1:0);
   if(!result&&!replies)replies+=(unsigned)reply(server,mode);
  }
  int expected=mode==1?HB_DNS_LOOKUP:mode==2||mode==4?HB_DNS_DEADLINE:mode==3?HB_DNS_CANCELLED:mode==5?HB_DNS_LIMIT:mode==6?HB_DNS_INPUT:1;
  assert(result==expected);
  if(result==1){
   assert(query.count==(mode==7?2u:1u));
   for(unsigned i=0;i<query.count;i++)assert(query.addresses[i].sin_family==AF_INET&&query.addresses[i].sin_port==htons(443)&&
    ntohl(query.addresses[i].sin_addr.s_addr)>=0x7f000001u&&ntohl(query.addresses[i].sin_addr.s_addr)<=0x7f000002u);
  }else assert(!query.count);
  hb_dns_release(&query);assert(!query.channel&&query.state==HB_DNS_EMPTY&&!query.count);assert(!close(server));
 }
 static const char message[]="stock async DNS local reply/NXDOMAIN/timeout/cancel/limit passed\n";
 return write(1,message,sizeof message-1)==(long)(sizeof message-1)?0:1;
}
