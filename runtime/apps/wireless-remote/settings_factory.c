#define _DEFAULT_SOURCE
#include "settings_factory.h"
#include "../../platform/player/wireless_host.h"
#include "../../platform/player/host_managed_service.h"
#include "../../platform/player/managed_host.h"
#include <unistd.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <fcntl.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
extern int factory_fcntl(int,int,...) __asm__("fcntl");
extern unsigned long pthread_self(void);
static int owner(struct wr_settings_factory *f){return f&&f->initialized&&f->owner_pid==(int)getpid()&&f->backend.owner==pthread_self();}
static int prepare(void *context,uint64_t *generation){
 struct wr_settings_factory *f=context;if(!owner(f)||f->fault_latched)return XW_PLAYER_UNAVAILABLE;
 uint64_t next;int rc=xw_player_host_next_generation(&next);if(rc)return rc;
 if(next>*generation)*generation=next;return 0;
}
static int mode(void *context){return owner(context)?xw_player_host_wireless_remote_mode():XW_WIRELESS_MODE_UNKNOWN;}
static int view_client_valid(struct wr_settings_factory *f){
 struct stat st;return f->owner_view_client>=3&&!fstat(f->owner_view_client,&st)&&S_ISSOCK(st.st_mode)&&
  (uint64_t)st.st_dev==f->owner_view_device&&(uint64_t)st.st_ino==f->owner_view_inode;
}
static int make_view(struct wr_settings_factory *f){
 if(f->owner_view.bound)return view_client_valid(f)&&f->owner_view.observing&&
  f->owner_view.lease.serial==f->radio.serial&&f->owner_view.lease.generation==f->radio.generation?0:XW_PLAYER_UNAVAILABLE;
 if(f->owner_view.policy||f->owner_view_client>=3)return XW_PLAYER_UNAVAILABLE;
 int pair[2];if(socketpair(AF_UNIX,SOCK_DGRAM,0,pair))return XW_PLAYER_UNAVAILABLE;
 for(unsigned i=0;i<2;i++){
  if(pair[i]<3){int copy=factory_fcntl(pair[i],F_DUPFD,3);close(pair[i]);pair[i]=copy;}
  if(pair[i]<3||pair[i]>65535||factory_fcntl(pair[i],F_SETFD,FD_CLOEXEC)<0||factory_fcntl(pair[i],F_SETFL,O_NONBLOCK)<0){
   for(unsigned j=0;j<2;j++)if(pair[j]>=0)close(pair[j]);return XW_PLAYER_UNAVAILABLE;
  }
 }
 struct stat st;int rc=fstat(pair[1],&st)||!S_ISSOCK(st.st_mode)?XW_PLAYER_UNAVAILABLE:
  xw_player_host_wireless_remote_view(&f->owner_view,pair[0],&f->radio);
 close(pair[0]);if(rc){close(pair[1]);return rc;}
 f->owner_view_client=pair[1];f->owner_view_device=st.st_dev;f->owner_view_inode=st.st_ino;return 0;
}
static int dispose_view(struct wr_settings_factory *f){
 if(f->owner_view_client>=3){
  if(!view_client_valid(f)||close(f->owner_view_client))return XW_PLAYER_UNAVAILABLE;
  f->owner_view_client=-1;
 }
 if(f->owner_view.policy){int rc=xw_mode_channel_close(&f->owner_view);if(rc)return XW_PLAYER_UNAVAILABLE;}
 memset(&f->owner_view,0,sizeof f->owner_view);f->owner_view_device=f->owner_view_inode=0;return 0;
}
static int admit(void *context){
 struct wr_settings_factory *f=context;
 if(!owner(f)||f->fault_latched||mode(f)!=XW_WIRELESS_MODE_ESPNOW||f->qualified(f->context)!=1)return 0;
 int rc=xw_player_host_wireless_remote_acquire(&f->radio);if(rc)return 0;f->held=1;
 if(make_view(f))return 0;
 if(f->forward_owner_view&&wr_supervisor_process_mode_view(&f->backend.process,f->owner_view_client,&f->radio))return 0;
 return 1;
}
static int release(struct wr_settings_factory *f){
 int rc=dispose_view(f);if(rc)return rc;
 rc=xw_player_host_wireless_remote_retired(&f->radio,1);if(rc)return rc;
 memset(&f->radio,0,sizeof f->radio);f->held=0;return 0;
}
int wr_settings_factory_bind(struct wr_settings_factory *f,uint64_t generation,void *context,int (*qualified)(void *)){
 if(!f||f->initialized||f->backend.phase||f->backend.process.state||f->held||!generation||!qualified)return XW_PLAYER_INVALID;
 f->context=context;f->qualified=qualified;f->owner_pid=(int)getpid();f->owner_view_client=-1;f->initialized=1;
 int rc=wr_settings_backend_bind(&f->backend,generation,f,admit,mode);
 if(rc){f->initialized=0;return rc;}
 rc=wr_settings_backend_prepare(&f->backend,prepare);
 if(rc){if(!wr_settings_backend_unbind(&f->backend))f->initialized=0;else f->fault_latched=1;return rc;}
 return 0;
}
int wr_settings_factory_tick(struct wr_settings_factory *f){
 if(!owner(f))return XW_PLAYER_BUSY;
 struct wr_settings_backend *b=&f->backend;
 if(f->owner_view.bound){
  int rc=xw_mode_channel_step(&f->owner_view);
  if(rc&&rc!=XW_MODE_PENDING){
   if(f->held)(void)xw_mode_policy_quiesce(f->owner_view.policy,&f->radio);
   f->fault_latched=1;f->error=XW_PLAYER_UNCERTAIN;(void)wr_settings_backend_request_stop(b);
  }
 }
 if(xw_player_host_original_exiting())(void)wr_settings_backend_cleanup_tick(b);
 if(b->phase==WR_SETTINGS_FAULT){
  if(b->process.state&&!b->process.reaped&&!b->process.stop_sent)(void)wr_supervisor_process_request_stop(&b->process);
  (void)xw_player_host_service_stop_generation(b->generation);
  if(f->held&&!f->fault_latched)(void)xw_player_host_wireless_remote_retired(&f->radio,0);
  f->fault_latched=1;f->error=b->error?b->error:XW_PLAYER_UNCERTAIN;return f->error;
 }
 if(f->fault_latched)return XW_PLAYER_UNAVAILABLE;
 /* The admission callback can reserve a logical lease before fork. If start
  * failed with no process object, no child/owner received that lease. */
 if(f->held&&b->phase==WR_SETTINGS_OFF&&!b->process.state){
  int rc=release(f);if(rc){f->fault_latched=1;return f->error=rc;}
 }
 if(f->held&&b->phase==WR_SETTINGS_RETIRED){
  if(b->process.state!=WR_PROCESS_CLOSED||!b->process.reaped||(b->process.status&&!b->process.startup_refused)||b->process.delivery>=0||b->process.stop_fd>=0||b->process.log_reader>=0){f->fault_latched=1;return f->error=XW_PLAYER_UNCERTAIN;}
  int rc=release(f);if(rc){f->fault_latched=1;return f->error=rc;}
 }
 if(b->phase==WR_SETTINGS_RETIRED&&!f->held){
  uint64_t next;int rc=xw_player_host_next_generation(&next);
  if(rc==XW_PLAYER_BUSY||rc==XW_PLAYER_CLOSED)return 0;
  if(rc)return f->error=rc;
  if(next<=b->generation){if(b->generation==UINT64_MAX)return f->error=XW_PLAYER_UNAVAILABLE;next=b->generation+1;}
  rc=wr_settings_backend_renew(b,next);if(rc)return f->error=rc;
 }
 return 0;
}
int wr_settings_factory_unbind(struct wr_settings_factory *f){
 if(!owner(f))return XW_PLAYER_BUSY;
 if(f->held||f->fault_latched||f->owner_view.policy||f->owner_view_client>=3)return XW_PLAYER_BUSY;
 int rc=wr_settings_backend_unbind(&f->backend);if(!rc)f->initialized=0;return rc;
}
int wr_settings_factory_owner_view(struct wr_settings_factory *f,uint64_t generation,int *fd,struct xw_wireless_lease *lease){
 if(!owner(f))return XW_PLAYER_BUSY;
 if(!fd||!lease)return XW_PLAYER_INVALID;
 if(generation!=f->backend.generation)return XW_PLAYER_STALE;
 if(!f->held||f->fault_latched||!f->owner_view.bound||!view_client_valid(f)||
    xw_mode_policy_data_allowed(f->owner_view.policy,&f->radio))return XW_PLAYER_UNAVAILABLE;
 *fd=f->owner_view_client;*lease=f->radio;return 0;
}
int wr_settings_factory_forward_owner_view(struct wr_settings_factory *f){
 if(!owner(f))return XW_PLAYER_BUSY;
 if(f->held||f->fault_latched||f->backend.phase!=WR_SETTINGS_OFF||f->backend.process.state||f->owner_view.policy)return XW_PLAYER_BUSY;
 f->forward_owner_view=1;return 0;
}
