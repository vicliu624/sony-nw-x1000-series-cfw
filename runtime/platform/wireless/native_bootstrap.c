#define _DEFAULT_SOURCE
#include "native_delivery.h"
#include "native_offer.h"
#include "native_boot.h"
#include "native_retirement.h"
#include <pthread.h>
#include <unistd.h>
#include <sys/socket.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
extern int bootstrap_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t bootstrap_send(int,const void *,size_t,int) __asm__("send");
extern ssize_t bootstrap_recv(int,void *,size_t,int) __asm__("recv");
/* Published by the GUI constructor before Sony creates its native worker.
 * Two bounded process-lifetime descriptors; no listener, path or RF power. */
static int pair[2]={-1,-1},gui_pid,prepared;
static unsigned long gui_thread;
static pthread_once_t claimed=PTHREAD_ONCE_INIT;
static int boot_consumed;
int xw_native_rf_gui_owner(void){
 return prepared&&gui_pid==(int)getpid()&&gui_thread==(unsigned long)pthread_self();
}
int xw_native_rf_bootstrap_gui(void){
 if(prepared)return gui_pid==(int)getpid()&&gui_thread==(unsigned long)pthread_self()?0:XW_MODE_WRONG_OWNER;
 int local[2];if(socketpair(AF_UNIX,SOCK_DGRAM,0,local))return XW_MODE_FAULT;
 for(unsigned i=0;i<2;i++){
  if(bootstrap_fcntl(local[i],F_SETFD,FD_CLOEXEC)<0||bootstrap_fcntl(local[i],F_SETFL,O_NONBLOCK)<0){close(local[0]);close(local[1]);return XW_MODE_FAULT;}
 }
 pair[0]=local[0];pair[1]=local[1];gui_pid=getpid();gui_thread=(unsigned long)pthread_self();prepared=1;return 0;
}
static void claim(void){
 if(xw_native_delivery_attach(pair[1]))return;
 struct xw_native_boot_observation observation;unsigned char raw[64];
 (void)xw_native_boot_observe(&observation);
 if(!xw_native_boot_encode(raw,&observation))(void)bootstrap_send(pair[1],raw,sizeof raw,MSG_DONTWAIT|MSG_NOSIGNAL);
}
int xw_native_rf_bootstrap_worker(void){
 if(!prepared||pthread_self()==gui_thread)return XW_MODE_DENIED;
 if(pthread_once(&claimed,claim))return XW_MODE_FAULT;
 return xw_native_delivery_attached()?0:XW_MODE_DENIED;
}
int xw_native_rf_publish(struct xw_wireless_mode_policy *p,int observation,const struct xw_wireless_lease *lease){
 if(!prepared||gui_pid!=(int)getpid()||gui_thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 return xw_native_offer_send(p,pair[0],observation,lease);
}
int xw_native_rf_boot_observation(struct xw_native_boot_observation *out){
 if(!out)return XW_MODE_INVALID;
 if(!prepared||gui_pid!=(int)getpid()||gui_thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 if(boot_consumed)return XW_MODE_STALE;
 unsigned char raw[65];ssize_t count=bootstrap_recv(pair[0],raw,sizeof raw,MSG_DONTWAIT|MSG_TRUNC);
 if(count<0)return errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR?XW_MODE_PENDING:XW_MODE_FAULT;
 boot_consumed=1;return xw_native_boot_decode(out,raw,(unsigned)count);
}
int xw_native_rf_retirement_receive(struct xw_native_retirement *out){
 if(!out)return XW_MODE_INVALID;if(!xw_native_rf_gui_owner())return XW_MODE_WRONG_OWNER;
 unsigned char raw[65];ssize_t count=bootstrap_recv(pair[0],raw,sizeof raw,MSG_DONTWAIT|MSG_TRUNC);
 if(count<0)return errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR?XW_MODE_PENDING:XW_MODE_FAULT;
 /* An explicitly pre-bound authority can legitimately precede WBS1 receipt. */
 if(count==64&&!memcmp(raw,"WBS1",4)){
  struct xw_native_boot_observation ignored;boot_consumed=1;
  int rc=xw_native_boot_decode(&ignored,raw,64);return rc?rc:XW_MODE_PENDING;
 }
 return xw_native_retirement_decode(out,raw,(unsigned)count);
}
