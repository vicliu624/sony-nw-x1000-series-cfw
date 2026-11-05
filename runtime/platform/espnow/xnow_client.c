#include "xnow_client.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int client_fcntl(int,int,...) __asm__("fcntl");
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static int alive(const struct xnow_client *c){return c&&c->used&&!c->fault&&c->pid==(int)getpid();}
static int identity(const struct xnow_client *c,unsigned i){
 int fd=i?c->output:c->input,flags=client_fcntl(fd,F_GETFL);struct stat st;
 return fd>=0&&flags>=0&&(flags&O_NONBLOCK)&&(flags&O_ACCMODE)==(i?O_WRONLY:O_RDONLY)&&
  !fstat(fd,&st)&&S_ISFIFO(st.st_mode)&&(uint64_t)st.st_dev==c->device[i]&&(uint64_t)st.st_ino==c->inode[i];
}
int xnow_client_close(struct xnow_client *c){
 if(!c||!c->used||c->pid!=(int)getpid())return XNOW_CLIENT_ARGUMENT;
 int rc=0;
 for(unsigned i=0;i<2;i++){int fd=i?c->output:c->input;if(fd>=0){if(!identity(c,i))rc=XNOW_CLIENT_IDENTITY;else if(close(fd))rc=XNOW_CLIENT_IO;}}
 wipe(c->request,sizeof c->request);wipe(c->response,sizeof c->response);wipe(&c->event,sizeof c->event);
 c->input=c->output=-1;c->fault=1;c->event_ready=0;c->request_bytes=c->received=c->sent=0;return rc;
}
static int fail(struct xnow_client *c,int reason){
 int uncertain=(c->pending&&c->sent)||c->awaiting||c->tx_request;
 xnow_client_close(c);return uncertain?XNOW_CLIENT_UNCERTAIN:reason;
}
int xnow_client_adopt(struct xnow_client *c,int input,int output){
 if(!c||c->used||input<0||output<0||input==output)return XNOW_CLIENT_ARGUMENT;
 int copies[2]={-1,-1};uint64_t device[2],inode[2];
 int original[2]={input,output};
 for(unsigned i=0;i<2;i++){
  struct stat st;int flags=client_fcntl(original[i],F_GETFL);
  if(flags<0||!(flags&O_NONBLOCK)||(flags&O_ACCMODE)!=(i?O_WRONLY:O_RDONLY)||fstat(original[i],&st)||!S_ISFIFO(st.st_mode))goto invalid;
  device[i]=(uint64_t)st.st_dev;inode[i]=(uint64_t)st.st_ino;
  int fd=client_fcntl(original[i],F_DUPFD,3);if(fd<0)goto invalid;
  copies[i]=fd;
  if(client_fcntl(fd,F_SETFD,FD_CLOEXEC))goto invalid;
 }
 if(device[0]==device[1]&&inode[0]==inode[1])goto invalid;
 memset(c,0,sizeof *c);c->input=copies[0];c->output=copies[1];c->pid=(int)getpid();c->used=1;c->needed=16;
 memcpy(c->device,device,sizeof device);memcpy(c->inode,inode,sizeof inode);
 close(input);close(output);return 0;
invalid:
 if(copies[0]>=0)close(copies[0]);if(copies[1]>=0)close(copies[1]);return XNOW_CLIENT_IDENTITY;
}
static int queue(struct xnow_client *c,unsigned operation,const uint8_t *body,size_t bytes,uint32_t *request){
 if(!request||!alive(c)||c->stopping||bytes>sizeof c->request-16)return XNOW_CLIENT_ARGUMENT;
 if(c->pending||(operation==4&&c->tx_request))return XNOW_CLIENT_PENDING;
 if(c->serial==UINT32_MAX)return XNOW_CLIENT_IDENTITY;
 wipe(c->request,sizeof c->request);memcpy(c->request,"XNC1",4);c->request[4]=(uint8_t)operation;
 c->pending=++c->serial;c->operation=operation;put32(c->request+8,c->pending);put32(c->request+12,(uint32_t)bytes);
 if(bytes)memcpy(c->request+16,body,bytes);
 if(operation==4)memcpy(c->pending_destination,body,6);
 c->request_bytes=16+bytes;c->sent=0;c->awaiting=0;if(operation==5)c->stopping=1;*request=c->pending;return 0;
}
static int mac_ok(const uint8_t *mac){unsigned any=0;for(unsigned i=0;i<6;i++)any|=mac[i];return any!=0;}
int xnow_client_peer(struct xnow_client *c,const struct xnow_client_peer *p,int modify,uint32_t *request){
 if(!p||!mac_ok(p->address)||p->channel>13||(p->version!=1&&p->version!=2)||p->encrypt>1||(p->encrypt&&(p->address[0]&1))||(modify!=0&&modify!=1))return XNOW_CLIENT_ARGUMENT;
 uint8_t body[26]={0};memcpy(body,p->address,6);body[6]=p->channel;body[7]=p->version;body[8]=p->encrypt;if(p->encrypt)memcpy(body+10,p->lmk,16);
 int rc=queue(c,modify?2:1,body,sizeof body,request);wipe(body,sizeof body);return rc;
}
int xnow_client_delete(struct xnow_client *c,const uint8_t mac[6],uint32_t *request){if(!mac||!mac_ok(mac))return XNOW_CLIENT_ARGUMENT;return queue(c,3,mac,6,request);}
int xnow_client_send(struct xnow_client *c,const uint8_t mac[6],const void *data,size_t bytes,uint32_t *request){
 if(!mac||!mac_ok(mac)||(!data&&bytes)||bytes>XNOW_CLIENT_PAYLOAD_MAX)return XNOW_CLIENT_ARGUMENT;
 uint8_t body[6+XNOW_CLIENT_PAYLOAD_MAX];memcpy(body,mac,6);if(bytes)memcpy(body+6,data,bytes);
 int rc=queue(c,4,body,6+bytes,request);wipe(body,6+bytes);return rc;
}
int xnow_client_request_stop(struct xnow_client *c,uint32_t *request){return queue(c,5,0,0,request);}
static int decode(struct xnow_client *c){
 const uint8_t *p=c->response;struct xnow_client_event event;memset(&event,0,sizeof event);
 if(!memcmp(p,"XNA1",4)){
  if(!c->awaiting||get32(p+4)!=c->pending||get32(p+12)!=c->operation)return XNOW_CLIENT_PROTOCOL;
  event.kind=XNOW_CLIENT_ACK;event.request=c->pending;event.operation=c->operation;uint32_t raw=get32(p+8);memcpy(&event.result,&raw,4);
  if(event.operation==4&&!event.result){c->tx_request=c->pending;memcpy(c->tx_destination,c->pending_destination,6);}
  c->awaiting=0;c->pending=0;
 }else if(!memcmp(p,"XNT1",4)){
  if(get32(p+4)!=32||!c->tx_request||get32(p+8)!=c->tx_request||memcmp(p+16,c->tx_destination,6)||p[22]||p[23])return XNOW_CLIENT_PROTOCOL;
  event.kind=XNOW_CLIENT_TX;event.request=c->tx_request;uint32_t raw=get32(p+12);memcpy(&event.result,&raw,4);
  memcpy(event.address,p+16,6);event.stock_status=get32(p+24);event.raw_fields=get32(p+28);c->tx_request=0;
 }else if(!memcmp(p,"XNR1",4)){
  if(c->needed<32||get32(p+4)!=c->needed||get32(p+8)||get32(p+28)||!mac_ok(p+12)||
     (p[18]!=1&&p[18]!=2)||!p[19]||(get32(p+24)&~3u)||get32(p+24)==3||
     (p[18]==1&&c->needed-32>250))return XNOW_CLIENT_PROTOCOL;
  event.kind=XNOW_CLIENT_RX;memcpy(event.address,p+12,6);event.version=p[18];event.elements=p[19];memcpy(event.random,p+20,4);event.flags=get32(p+24);event.bytes=c->needed-32;
 }else return XNOW_CLIENT_PROTOCOL;
 c->event=event;c->event_ready=1;return 0;
}
int xnow_client_step(struct xnow_client *c){
 if(!alive(c))return XNOW_CLIENT_ARGUMENT;
 if(!identity(c,0)||!identity(c,1))return fail(c,XNOW_CLIENT_IDENTITY);
 if(c->event_ready)return 0;
 struct pollfd fds[2]={{c->input,POLLIN,0},{c->output,POLLOUT,0}};int ready=poll(fds,2,0);
 if(ready<0)return errno==EINTR?XNOW_CLIENT_PENDING:fail(c,XNOW_CLIENT_IO);
 if((fds[0].revents|fds[1].revents)&(POLLHUP|POLLERR|POLLNVAL))return fail(c,XNOW_CLIENT_IO);
 if(c->request_bytes){
  if(!(fds[1].revents&POLLOUT))return XNOW_CLIENT_PENDING;
  ssize_t n=write(c->output,c->request+c->sent,c->request_bytes-c->sent);
  if(n<0&&(errno==EINTR||errno==EAGAIN))return XNOW_CLIENT_PENDING;
  if(n<=0)return fail(c,XNOW_CLIENT_IO);c->sent+=(size_t)n;
  if(c->sent==c->request_bytes){wipe(c->request,sizeof c->request);c->request_bytes=0;c->sent=0;c->awaiting=1;}
  return XNOW_CLIENT_PENDING;
 }
 if(!(fds[0].revents&POLLIN))return XNOW_CLIENT_AGAIN;
 ssize_t n=read(c->input,c->response+c->received,c->needed-c->received);
 if(n<0&&(errno==EINTR||errno==EAGAIN))return XNOW_CLIENT_PENDING;
 if(n<=0)return fail(c,XNOW_CLIENT_IO);c->received+=(size_t)n;
 if(c->received==16&&c->needed==16){
  if(!memcmp(c->response,"XNA1",4))c->needed=16;
  else if(!memcmp(c->response,"XNT1",4)&&get32(c->response+4)==32)c->needed=32;
  else if(!memcmp(c->response,"XNR1",4)&&get32(c->response+4)>=32&&get32(c->response+4)<=sizeof c->response)c->needed=get32(c->response+4);
  else return fail(c,XNOW_CLIENT_PROTOCOL);
 }
 if(c->received<c->needed)return XNOW_CLIENT_PENDING;
 int rc=decode(c);return rc?fail(c,rc):0;
}
int xnow_client_take(struct xnow_client *c,struct xnow_client_event *event,void *data,size_t capacity){
 if(!alive(c)||!event)return XNOW_CLIENT_ARGUMENT;if(!c->event_ready)return XNOW_CLIENT_AGAIN;
 if(c->event.bytes>capacity||(!data&&c->event.bytes))return XNOW_CLIENT_ARGUMENT;
 if(c->event.bytes)memcpy(data,c->response+32,c->event.bytes);*event=c->event;
 wipe(c->response,sizeof c->response);wipe(&c->event,sizeof c->event);c->received=0;c->needed=16;c->event_ready=0;return 0;
}
