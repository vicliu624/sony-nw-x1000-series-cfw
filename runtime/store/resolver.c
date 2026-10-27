#define _GNU_SOURCE
#include "resolver.h"
#include "https_url.h"
#include <netdb.h>
#include <poll.h>
#include <string.h>
#include <errno.h>
typedef char hb_dns_fd_mask_16[(ARES_GETSOCK_MAXNUM==16&&sizeof(int)==4)?1:-1];
static void destroy(struct hb_dns_query *q){if(q->channel){ares_cancel(q->channel);ares_destroy(q->channel);q->channel=0;}}
static int fail(struct hb_dns_query *q,int error){q->state=HB_DNS_FAILED;q->error=error;q->count=0;destroy(q);return error;}
static int budget(struct hb_dns_query *q,unsigned *wait){
 if(q->stop&&*q->stop)return HB_DNS_CANCELLED;
 int result=hb_transfer_deadline_remaining(q->deadline,wait);return result<0?HB_DNS_CLOCK:result?0:HB_DNS_DEADLINE;
}
static void answer(void *context,int status,int timeouts,struct hostent *host){
 struct hb_dns_query *q=context;(void)timeouts;
 if(q->state!=HB_DNS_ACTIVE)return;
 q->ares_status=status;q->count=0;
 if(status!=ARES_SUCCESS){q->state=HB_DNS_FAILED;q->error=HB_DNS_LOOKUP;return;}
 if(!host||host->h_addrtype!=AF_INET||host->h_length!=4||!host->h_addr_list){q->state=HB_DNS_FAILED;q->error=HB_DNS_FORMAT;return;}
 for(unsigned i=0;host->h_addr_list[i];i++){
  if(i==HB_DNS_MAX_ADDRESSES){q->count=0;q->state=HB_DNS_FAILED;q->error=HB_DNS_LIMIT;return;}
  memset(q->addresses+i,0,sizeof q->addresses[i]);q->addresses[i].sin_family=AF_INET;q->addresses[i].sin_port=htons((unsigned short)q->port);
  memcpy(&q->addresses[i].sin_addr,host->h_addr_list[i],4);q->count++;
 }
 if(!q->count){q->state=HB_DNS_FAILED;q->error=HB_DNS_FORMAT;return;}
 q->state=HB_DNS_READY;
}
void hb_dns_init(struct hb_dns_query *q){if(q)memset(q,0,sizeof *q);}
void hb_dns_release(struct hb_dns_query *q){if(q){q->state=HB_DNS_FAILED;destroy(q);q->count=0;q->state=HB_DNS_EMPTY;}}
int hb_dns_begin(struct hb_dns_query *q,const char *name,unsigned port,struct hb_transfer_deadline *deadline,volatile int *stop,const struct ares_options *options,int mask){
 if(!q||q->state!=HB_DNS_EMPTY||!name||!deadline||!port||port>65535)return HB_DNS_INPUT;
 char url[264];unsigned n=0;
 while(n<=253&&name[n]){char c=name[n];if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='.'))return HB_DNS_INPUT;n++;}
 if(!n||n>253)return HB_DNS_INPUT;
 const char *prefix="https://";for(unsigned i=0;i<8;i++)url[i]=prefix[i];for(unsigned i=0;i<n;i++)url[8+i]=name[i];url[8+n]='/';url[9+n]=0;
 struct hb_https_url parsed;if(hb_https_url_parse(url,&parsed)||strcmp(parsed.path,"/")||parsed.port!=443)return HB_DNS_INPUT;
 q->deadline=deadline;q->stop=stop;q->port=port;q->error=q->ares_status=0;q->count=0;strcpy(q->name,parsed.host);
 unsigned wait;int result=budget(q,&wait);if(result)return fail(q,result);
 ares_channel channel=0;
 if(options){struct ares_options copy=*options;result=ares_init_options(&channel,&copy,mask);}else result=ares_init(&channel);
 if(result!=ARES_SUCCESS){q->ares_status=result;return fail(q,HB_DNS_LOOKUP);}
 q->channel=channel;
 q->state=HB_DNS_ACTIVE;ares_gethostbyname(q->channel,q->name,AF_INET,answer,q);
 if(q->state==HB_DNS_FAILED)return fail(q,q->error);
 result=budget(q,&wait);if(result)return fail(q,result);
 return q->state==HB_DNS_READY?1:0;
}
int hb_dns_step(struct hb_dns_query *q,unsigned cap){
 if(!q||cap>1000)return HB_DNS_INPUT;
 if(q->state==HB_DNS_FAILED)return q->error;
 if(q->state!=HB_DNS_ACTIVE&&q->state!=HB_DNS_READY)return HB_DNS_INPUT;
 unsigned wait;int result=budget(q,&wait);if(result)return fail(q,result);if(wait>cap)wait=cap;
 if(q->state==HB_DNS_READY)return 1;
 int sockets[ARES_GETSOCK_MAXNUM];struct pollfd descriptors[ARES_GETSOCK_MAXNUM];unsigned count=0;
 unsigned bits=(unsigned)ares_getsock(q->channel,sockets,ARES_GETSOCK_MAXNUM);
 for(unsigned i=0;i<ARES_GETSOCK_MAXNUM;i++){
  short events=0;if(bits&(1u<<i))events|=POLLIN;if(bits&(1u<<(i+16)))events|=POLLOUT;
  if(events){if(sockets[i]<0)return fail(q,HB_DNS_IO);descriptors[count].fd=sockets[i];descriptors[count].events=events;descriptors[count].revents=0;count++;}
 }
 result=poll(descriptors,count,(int)wait);
 if(result<0&&errno!=EINTR)return fail(q,HB_DNS_IO);
 int timed=budget(q,&wait);if(timed)return fail(q,timed);
 if(result>0)for(unsigned i=0;i<count&&q->state==HB_DNS_ACTIVE;i++){
  short events=descriptors[i].revents;if(events&POLLNVAL)return fail(q,HB_DNS_IO);
  if(events)ares_process_fd(q->channel,events&(POLLIN|POLLERR|POLLHUP)?descriptors[i].fd:ARES_SOCKET_BAD,events&POLLOUT?descriptors[i].fd:ARES_SOCKET_BAD);
 }
 else if(!result)ares_process_fd(q->channel,ARES_SOCKET_BAD,ARES_SOCKET_BAD);
 if(q->state==HB_DNS_FAILED)return fail(q,q->error);
 timed=budget(q,&wait);if(timed)return fail(q,timed);
 return q->state==HB_DNS_READY?1:0;
}
