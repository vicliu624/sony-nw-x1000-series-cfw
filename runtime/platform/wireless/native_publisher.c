#define _DEFAULT_SOURCE
#include "native_publisher.h"
#include "native_delivery.h"
#include <sys/socket.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
extern int publisher_fcntl(int,int,...) __asm__("fcntl");
static int owner(struct xw_native_publisher *p){
 struct xw_wireless_mode_snapshot s;return !p||!p->policy?XW_MODE_INVALID:xw_mode_policy_snapshot(p->policy,&s);
}
static int same(const struct xw_wireless_lease *a,const struct xw_wireless_lease *b){
 return a->generation==b->generation&&a->serial==b->serial&&a->consumer==b->consumer&&a->mode==b->mode;
}
static int close_client(struct xw_native_publisher *p){
 if(p->client<0)return 0;struct stat s;
 if(fstat(p->client,&s)||!S_ISSOCK(s.st_mode)||(uint64_t)s.st_dev!=p->device||(uint64_t)s.st_ino!=p->inode){p->client=-1;return XW_MODE_FAULT;}
 int rc=close(p->client);p->client=-1;return rc?XW_MODE_FAULT:0;
}
static int fail(struct xw_native_publisher *p){
 p->fault=1;(void)close_client(p);
 if(p->channel.policy&&p->channel.bound)(void)xw_mode_channel_close(&p->channel);
 return XW_MODE_FAULT;
}
int xw_native_publisher_bind(struct xw_native_publisher *p,struct xw_wireless_mode_policy *authority){
 if(!p||p->policy)return XW_MODE_INVALID;
 struct xw_wireless_mode_snapshot s;int rc=xw_mode_policy_snapshot(authority,&s);if(rc)return rc;
 memset(p,0,sizeof *p);p->policy=authority;p->client=-1;return 0;
}
int xw_native_publisher_prepare(struct xw_native_publisher *p,const struct xw_wireless_lease *lease){
 int rc=owner(p);if(rc)return rc;if(p->fault||p->closed)return XW_MODE_FAULT;
 if(!lease||lease->mode!=XW_WIRELESS_MODE_WIFI)return XW_MODE_INVALID;
 rc=xw_mode_policy_data_allowed(p->policy,lease);if(rc)return rc;
 if(p->issued&&!same(&p->lease,lease)){
  rc=xw_mode_policy_owns(p->policy,&p->lease);if(!rc)return XW_MODE_BUSY;
  if(rc!=XW_MODE_STALE)return fail(p);
  if(xw_mode_channel_close(&p->channel)||close_client(p))return fail(p);
  memset(&p->channel,0,sizeof p->channel);p->issued=p->published=0;
 }
 if(!p->issued){
  int pair[2];if(socketpair(AF_UNIX,SOCK_DGRAM,0,pair))return fail(p);
  struct stat s;
  if(publisher_fcntl(pair[1],F_SETFD,FD_CLOEXEC)<0||fstat(pair[1],&s)){close(pair[0]);close(pair[1]);return fail(p);}
  rc=xw_mode_channel_open(&p->channel,p->policy,pair[0],lease->consumer,XW_MODE_GRANT_READ);close(pair[0]);
  if(rc){close(pair[1]);return fail(p);}
  rc=xw_mode_channel_observe(&p->channel,lease);
  if(rc){close(pair[1]);(void)xw_mode_channel_close(&p->channel);return fail(p);}
  p->client=pair[1];p->device=s.st_dev;p->inode=s.st_ino;p->lease=*lease;p->issued=1;
 }
 if(p->published)return 0;
 rc=xw_native_rf_publish(p->policy,p->client,&p->lease);
 if(rc==XW_MODE_PENDING)return rc;
 if(rc||close_client(p))return fail(p);
 p->published=1;return 0;
}
int xw_native_publisher_step(struct xw_native_publisher *p){
 if(!p||!p->policy)return XW_MODE_INVALID;if(p->fault||p->closed)return XW_MODE_FAULT;
 if(!p->issued)return owner(p);
 int rc=xw_mode_channel_step(&p->channel);
 if(rc==XW_MODE_WRONG_OWNER||rc==XW_MODE_INVALID)return rc;
 return rc?fail(p):0;
}
int xw_native_publisher_close(struct xw_native_publisher *p){
 int rc=owner(p);if(rc)return rc;if(p->closed)return 0;
 int channel=p->channel.policy?xw_mode_channel_close(&p->channel):0;
 int client=close_client(p);p->closed=1;
 return channel||client?XW_MODE_FAULT:0;
}
int xw_native_publisher_retired(struct xw_native_publisher *p,const struct xw_wireless_lease *lease){
 int rc=owner(p);if(rc)return rc;if(!lease||p->closed)return XW_MODE_INVALID;
 if(p->issued&&!same(&p->lease,lease))return XW_MODE_STALE;
 rc=xw_mode_policy_owns(p->policy,lease);if(rc!=XW_MODE_STALE)return rc?rc:XW_MODE_BUSY;
 if(p->channel.policy&&xw_mode_channel_close(&p->channel))return fail(p);
 if(close_client(p))return fail(p);
 memset(&p->channel,0,sizeof p->channel);memset(&p->lease,0,sizeof p->lease);
 p->issued=p->published=p->fault=0;return 0;
}
