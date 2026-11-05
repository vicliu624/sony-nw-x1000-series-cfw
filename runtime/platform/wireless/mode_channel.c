#define _DEFAULT_SOURCE
#include "mode_channel.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <poll.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
extern int mode_fcntl(int,int,...) __asm__("fcntl");
extern int mode_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern ssize_t mode_send(int,const void *,size_t,int) __asm__("send");
extern ssize_t mode_recv(int,void *,size_t,int) __asm__("recv");
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i));}
static void put64(unsigned char *p,uint64_t n){for(unsigned i=0;i<8;i++)p[i]=(unsigned char)(n>>(8*i));}
static uint32_t get32(const unsigned char *p){uint32_t n=0;for(unsigned i=0;i<4;i++)n|=(uint32_t)p[i]<<(8*i);return n;}
static uint64_t get64(const unsigned char *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n;}
int xw_mode_reply_decode(struct xw_mode_reply *out,const unsigned char *raw,unsigned length,uint32_t op,uint64_t serial){
 if(!out||!raw||length!=80||!serial||op<XW_MODE_QUERY||op>XW_MODE_RELEASE||memcmp(raw,"WMS1",4))return XW_MODE_INVALID;
 if(get32(raw+4)!=op||get64(raw+8)!=serial)return XW_MODE_STALE;
 for(unsigned i=72;i<80;i++)if(raw[i])return XW_MODE_INVALID;
 struct xw_mode_reply r;memset(&r,0,sizeof r);
 r.operation=op;r.serial=serial;r.result=(int32_t)get32(raw+16);r.phase=get32(raw+20);
 r.selected=(int32_t)get32(raw+24);r.requested=(int32_t)get32(raw+28);
 r.active=get32(raw+32);r.off_verified=get32(raw+36);r.generation=get64(raw+40);
 r.lease.generation=r.generation;r.lease.serial=get64(raw+48);r.lease.consumer=get64(raw+56);
 r.lease.mode=(int32_t)get32(raw+64);r.owned=get32(raw+68);
 if(r.result<XW_MODE_WRONG_OWNER||r.result>XW_MODE_PENDING||r.phase<XW_MODE_UNVERIFIED||r.phase>XW_MODE_FAILED||
    r.selected<XW_WIRELESS_MODE_UNKNOWN||r.selected>XW_WIRELESS_MODE_ESPNOW||
    r.requested<XW_WIRELESS_MODE_UNKNOWN||r.requested>XW_WIRELESS_MODE_ESPNOW||
    r.active<0||r.active>1||r.off_verified<0||r.off_verified>1||r.owned<0||r.owned>1||!r.generation||
    (r.active&&r.off_verified))return XW_MODE_INVALID;
 if(r.owned){
  if(!r.active||!r.lease.serial||!r.lease.consumer||
     (r.lease.mode!=XW_WIRELESS_MODE_WIFI&&r.lease.mode!=XW_WIRELESS_MODE_ESPNOW))return XW_MODE_INVALID;
 }else if(r.lease.serial||r.lease.consumer||r.lease.mode!=XW_WIRELESS_MODE_UNKNOWN)return XW_MODE_INVALID;
 *out=r;return 0;
}
int xw_mode_reply_data_allowed(const struct xw_mode_reply *r){
 return r&&r->operation==XW_MODE_QUERY&&!r->result&&r->phase==XW_MODE_STABLE&&r->active==1&&r->owned==1&&
        !r->off_verified&&r->generation&&r->lease.generation==r->generation&&r->lease.serial&&r->lease.consumer&&
        (r->selected==XW_WIRELESS_MODE_WIFI||r->selected==XW_WIRELESS_MODE_ESPNOW)&&
        r->selected==r->requested&&r->selected==r->lease.mode?0:XW_MODE_DENIED;
}
static int request_valid(uint32_t op,uint64_t serial,int mode){
 if(!serial||op<XW_MODE_QUERY||op>XW_MODE_RELEASE)return 0;
 if(op==XW_MODE_QUERY||op==XW_MODE_RELEASE)return mode==0;
 return mode>=XW_WIRELESS_MODE_OFF&&mode<=XW_WIRELESS_MODE_ESPNOW;
}
int xw_mode_request_encode(unsigned char out[32],uint32_t op,uint64_t serial,int mode){
 if(!out||!request_valid(op,serial,mode))return XW_MODE_INVALID;
 memset(out,0,32);memcpy(out,"WMC1",4);put32(out+4,op);put64(out+8,serial);put32(out+16,(uint32_t)mode);return 0;
}
static int identity(struct xw_mode_channel *c){struct stat s;return c->fd>=3&&!fstat(c->fd,&s)&&S_ISSOCK(s.st_mode)&&(uint64_t)s.st_dev==c->device&&(uint64_t)s.st_ino==c->inode;}
static int owner(struct xw_mode_channel *c){struct xw_wireless_mode_snapshot s;return !c||!c->policy?XW_MODE_INVALID:xw_mode_policy_snapshot(c->policy,&s);}
static int fail(struct xw_mode_channel *c){
 if(c->held)(void)xw_mode_policy_quiesce(c->policy,&c->lease);
 if(identity(c))close(c->fd);c->fd=-1;c->bound=0;c->fault=1;return XW_MODE_FAULT;
}
int xw_mode_channel_open(struct xw_mode_channel *c,struct xw_wireless_mode_policy *p,int fd,uint64_t consumer,uint32_t grants){
 struct xw_wireless_mode_snapshot snapshot;int rc=xw_mode_policy_snapshot(p,&snapshot);if(rc)return rc;
 if(!c||c->policy||fd<3||!consumer||!(grants&XW_MODE_GRANT_READ)||(grants&~15u))return XW_MODE_INVALID;
 struct sockaddr_un peer;int kind=0;socklen_t size=sizeof kind;struct stat s;
 if(mode_getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&size)||size!=sizeof kind||kind!=SOCK_DGRAM)return XW_MODE_INVALID;
 size=sizeof peer;memset(&peer,0,sizeof peer);
 if(getpeername(fd,(struct sockaddr *)&peer,&size)||size<sizeof peer.sun_family||peer.sun_family!=AF_UNIX||fstat(fd,&s)||!S_ISSOCK(s.st_mode))return XW_MODE_INVALID;
 int copy=mode_fcntl(fd,F_DUPFD,3);if(copy<0)return XW_MODE_FAULT;
 if(mode_fcntl(copy,F_SETFD,FD_CLOEXEC)<0||mode_fcntl(copy,F_SETFL,O_NONBLOCK)<0){close(copy);return XW_MODE_FAULT;}
 memset(c,0,sizeof *c);c->policy=p;c->consumer=consumer;c->grants=grants;c->fd=copy;c->device=s.st_dev;c->inode=s.st_ino;c->bound=1;return 0;
}
int xw_mode_channel_observe(struct xw_mode_channel *c,const struct xw_wireless_lease *lease){
 int rc=owner(c);if(rc)return rc;
 if(!c->bound||c->fault||c->held||c->observing||c->pending||c->last_serial||c->grants!=XW_MODE_GRANT_READ||
    !lease||lease->consumer!=c->consumer)return XW_MODE_INVALID;
 rc=xw_mode_policy_data_allowed(c->policy,lease);if(rc)return rc;
 c->lease=*lease;c->observing=1;return 0;
}
static void reply(struct xw_mode_channel *c,uint32_t op,uint64_t serial,int result){
 struct xw_wireless_mode_snapshot s;(void)xw_mode_policy_snapshot(c->policy,&s);
 memset(c->reply,0,80);memcpy(c->reply,"WMS1",4);put32(c->reply+4,op);put64(c->reply+8,serial);put32(c->reply+16,(uint32_t)result);
 put32(c->reply+20,s.phase);put32(c->reply+24,(uint32_t)s.selected);put32(c->reply+28,(uint32_t)s.requested);
 put32(c->reply+32,s.active);put32(c->reply+36,s.off_verified);put64(c->reply+40,c->policy->generation);
 put32(c->reply+64,(uint32_t)XW_WIRELESS_MODE_UNKNOWN);
 if((c->held||c->observing)&&!xw_mode_policy_owns(c->policy,&c->lease)){
  put64(c->reply+48,c->lease.serial);put64(c->reply+56,c->lease.consumer);put32(c->reply+64,(uint32_t)c->lease.mode);put32(c->reply+68,1);
 }
 c->pending=1;
}
static int dispatch(struct xw_mode_channel *c,uint32_t op,int mode){
 switch(op){
 case XW_MODE_QUERY:return c->grants&XW_MODE_GRANT_READ?0:XW_MODE_DENIED;
 case XW_MODE_SELECT:return c->grants&XW_MODE_GRANT_SELECT?xw_mode_policy_request(c->policy,mode):XW_MODE_DENIED;
 case XW_MODE_ACQUIRE:
  if(c->held)return XW_MODE_BUSY;
  if((mode==XW_WIRELESS_MODE_WIFI&&!(c->grants&XW_MODE_GRANT_WIFI))||
     (mode==XW_WIRELESS_MODE_ESPNOW&&!(c->grants&XW_MODE_GRANT_ESPNOW)))return XW_MODE_DENIED;
  {int rc=xw_mode_policy_acquire(c->policy,mode,c->consumer,&c->lease);if(!rc)c->held=1;return rc;}
 case XW_MODE_RELEASE:return c->held?xw_mode_policy_quiesce(c->policy,&c->lease):XW_MODE_STALE;
 default:return XW_MODE_INVALID;
 }
}
int xw_mode_channel_step(struct xw_mode_channel *c){
 int rc=owner(c);if(rc)return rc;if(!c->bound||c->fault)return XW_MODE_FAULT;
 if(c->pending){
  if(!identity(c))return fail(c);
  ssize_t n=mode_send(c->fd,c->reply,80,MSG_DONTWAIT|MSG_NOSIGNAL);
  if(n==80){c->pending=0;return 0;}
  return n<0&&(errno==EAGAIN||errno==EINTR)?0:fail(c);
 }
 struct pollfd event={c->fd,POLLIN,0};int polled=poll(&event,1,0);
 if(polled<0)return errno==EINTR?0:fail(c);if(!polled)return 0;
 if(!identity(c))return fail(c);
 unsigned char raw[33];ssize_t n=mode_recv(c->fd,raw,sizeof raw,MSG_DONTWAIT);
 if(n<0)return errno==EAGAIN||errno==EINTR?0:fail(c);
 if(n!=32||memcmp(raw,"WMC1",4))return fail(c);
 uint32_t op=get32(raw+4);uint64_t serial=get64(raw+8);int mode=(int32_t)get32(raw+16);
 for(unsigned i=20;i<32;i++)if(raw[i])return fail(c);
 if(!request_valid(op,serial,mode))return fail(c);
 if(serial==c->last_serial&&!memcmp(raw,c->last_request,32)){
  memcpy(c->reply,c->last_reply,80);c->pending=1;return 0;
 }
 if(serial<=c->last_serial){reply(c,op,serial,XW_MODE_STALE);return 0;}
 rc=dispatch(c,op,mode);reply(c,op,serial,rc);c->last_serial=serial;
 memcpy(c->last_request,raw,32);memcpy(c->last_reply,c->reply,80);return 0;
}
int xw_mode_channel_retired(struct xw_mode_channel *c,int verified){
 int rc=owner(c);if(rc)return rc;if(!c->held)return XW_MODE_STALE;
 rc=xw_mode_policy_release(c->policy,&c->lease,verified);if(!rc)c->held=0;return rc;
}
int xw_mode_channel_close(struct xw_mode_channel *c){
 int rc=owner(c);if(rc)return rc;
 if(c->held)(void)xw_mode_policy_quiesce(c->policy,&c->lease);
 if(c->bound){if(!identity(c))return fail(c);if(close(c->fd))return fail(c);c->fd=-1;c->bound=0;}
 return c->held?XW_MODE_PENDING:0;
}
