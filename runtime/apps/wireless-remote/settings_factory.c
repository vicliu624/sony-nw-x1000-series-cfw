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
#ifdef WR_PAIRING_PROCESS
#include "../../store/deadline.h"
#include "run_profile.h"
#include "pairing_auto.h"
#ifdef WR_PAIRING_TRACE
extern void xw_player_pairing_trace(unsigned,int);
extern void xw_player_pairing_trace_radio(unsigned,int,const uint32_t[6]);
extern void xw_player_pairing_trace_exit(const struct wr_supervisor_process *);
#endif
#endif
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
static int mode(void *context){
 struct wr_settings_factory *f=context;
 if(!owner(f))return XW_WIRELESS_MODE_UNKNOWN;
 int selected=xw_player_host_wireless_remote_mode();
 if(!f->shared_wifi)return selected;
 /* Backend admission uses ESP-NOW as the transport capability. The radio
  * observation sent to the shared owner still describes the actual Wi-Fi lease. */
 return selected==XW_WIRELESS_MODE_WIFI?XW_WIRELESS_MODE_ESPNOW:XW_WIRELESS_MODE_UNKNOWN;
}
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
static int acquire_radio(struct wr_settings_factory *f){
 if(!f->shared_wifi)return xw_player_host_wireless_remote_acquire(&f->radio);
 int rc=xw_player_host_wireless_shared_acquire(&f->radio,&f->shared_ticket);
#ifdef WR_REMOTE_ROOT_COLD
 if(rc==XW_MODE_DENIED)rc=xw_player_host_wireless_cold_acquire(&f->radio);
#endif
 return rc;
}
static int admit(void *context){
 struct wr_settings_factory *f=context;
 if(!owner(f)||f->fault_latched||mode(f)!=XW_WIRELESS_MODE_ESPNOW||f->qualified(f->context)!=1)return 0;
#ifdef WR_PAIRING_PROCESS
 if(f->pairing.owner||f->pairing_store_request==2)return 0;
#endif
 int rc=f->held?0:acquire_radio(f);
 if(rc)return 0;f->held=1;
 if(make_view(f))return 0;
 if(f->forward_owner_view&&wr_supervisor_process_mode_view(&f->backend.process,f->owner_view_client,&f->radio))return 0;
 return 1;
}
static int release(struct wr_settings_factory *f){
 int rc=dispose_view(f);if(rc)return rc;
 rc=f->shared_ticket?xw_player_host_wireless_shared_retired(f->shared_ticket):
                   xw_player_host_wireless_remote_retired(&f->radio,1);
 if(rc)return rc;
 f->shared_ticket=0;
 memset(&f->radio,0,sizeof f->radio);f->held=0;return 0;
}
#ifdef WR_PAIRING_PROCESS
enum {PAIR_STORE_STAGING=1,PAIR_STORE_WAIT_RECEIPT,PAIR_STORE_RECEIPT_SEEN,PAIR_STORE_PUBLISHING};
static void clear_pairing(struct wr_settings_factory *f){
 wr_walkman_pairing_close(&f->pairing_state);
 f->pairing_commit_pending=0;
 f->pairing_commit_sent_ms=0;
 volatile uint8_t *p=(volatile uint8_t *)&f->pairing_keys;
 for(unsigned i=0;i<sizeof f->pairing_keys;i++)p[i]=0;
}
int wr_settings_factory_pairing_start(struct wr_settings_factory *f,const uint8_t cookie[16]){
 if(!owner(f)||!cookie)return XW_PLAYER_INVALID;
 if(f->fault_latched||!f->shared_wifi||f->qualified(f->context)!=1)return XW_PLAYER_UNAVAILABLE;
 if(f->held||f->pairing.owner||f->pairing_store_request||f->backend.pending_enabled||f->backend.phase!=WR_SETTINGS_OFF)return XW_PLAYER_BUSY;
 int rc=acquire_radio(f);
 if(rc)return XW_PLAYER_UNAVAILABLE;
 f->held=1;
 f->pairing_saved=0;
 rc=make_view(f);
 if(!rc)rc=wr_pairing_process_start(&f->pairing,f->owner_view_client,&f->radio,cookie);
 if(rc==XW_PLAYER_ACCEPTED)return rc;
 if(!f->pairing.owner&&!release(f))return rc;
 f->fault_latched=1;return f->error=XW_PLAYER_UNCERTAIN;
}
int wr_settings_factory_pairing_stop(struct wr_settings_factory *f){
 if(!owner(f))return XW_PLAYER_INVALID;
 clear_pairing(f);
 return f->pairing.owner?wr_pairing_process_stop(&f->pairing):0;
}
int wr_settings_factory_pairing_offer(struct wr_settings_factory *f,const uint8_t secret[16],const uint8_t nonce[16]){
 static const uint8_t broadcast[6]={255,255,255,255,255,255};
 if(!owner(f)||!secret||!nonce)return XW_PLAYER_INVALID;
 if(!f->pairing.owner||!f->pairing.client.used||f->fault_latched)return XW_PLAYER_UNAVAILABLE;
 unsigned long long now;
 if(hb_monotonic_millis(&now))return XW_PLAYER_UNAVAILABLE;
 struct wr_walkman_pairing next=f->pairing_state;
 uint8_t offer[WR_PAIRING_CONFIRM_BYTES];
 int rc=wr_walkman_pairing_offer(&next,secret,nonce,offer,now);
 if(rc){wr_walkman_pairing_close(&next);return XW_PLAYER_STALE;}
 uint32_t request;
 rc=xnow_client_send(&f->pairing.client,broadcast,offer,sizeof offer,&request);
 if(!rc)f->pairing_state=next;
 wr_walkman_pairing_close(&next);
 return !rc?XW_PLAYER_ACCEPTED:rc==XNOW_CLIENT_PENDING?XW_PLAYER_BUSY:XW_PLAYER_IO;
}
int wr_settings_factory_pair_auto_offer(struct wr_settings_factory *f,const uint8_t private_key[32],const uint8_t nonce[16]){
 static const uint8_t broadcast[6]={255,255,255,255,255,255};
 if(!owner(f)||!private_key||!nonce)return XW_PLAYER_INVALID;
 if(!f->pairing.owner||!f->pairing.client.used||f->fault_latched)return XW_PLAYER_UNAVAILABLE;
 unsigned long long now;
 if(hb_monotonic_millis(&now))return XW_PLAYER_UNAVAILABLE;
 struct wr_walkman_pairing next=f->pairing_state;
 uint8_t offer[WR_PAIR_AUTO_OFFER_BYTES];
 int rc=wr_walkman_pair_auto_offer(&next,private_key,nonce,offer,now);
 if(rc){wr_walkman_pairing_close(&next);return XW_PLAYER_STALE;}
 uint32_t request;
 rc=xnow_client_send(&f->pairing.client,broadcast,offer,sizeof offer,&request);
 if(!rc)f->pairing_state=next;
 wr_walkman_pairing_close(&next);
 return !rc?XW_PLAYER_ACCEPTED:rc==XNOW_CLIENT_PENDING?XW_PLAYER_BUSY:XW_PLAYER_IO;
}
int wr_settings_factory_pairing_commit(struct wr_settings_factory *f){
 if(!owner(f)||f->pairing_state.phase!=WR_PAIRING_VERIFIED||f->pairing_commit_pending||
    !f->pairing.owner||!f->pairing.client.used||f->fault_latched)return XW_PLAYER_UNAVAILABLE;
 uint8_t record[WR_PAIRING_RECORD_BYTES];
 if(wr_pairing_record_encode(record,f->pairing_state.transcript.controller,&f->pairing_keys,f->pairing.handoff.cookie))
  return XW_PLAYER_INVALID;
 uint32_t request;
 int rc=xnow_client_pairing_store(&f->pairing.client,0,record,sizeof record,&request);
 volatile uint8_t *p=record;for(unsigned i=0;i<sizeof record;i++)p[i]=0;
 if(!rc)f->pairing_commit_pending=PAIR_STORE_STAGING;
 return !rc?XW_PLAYER_ACCEPTED:rc==XNOW_CLIENT_PENDING?XW_PLAYER_BUSY:XW_PLAYER_IO;
}
static int send_pairing_commit(struct wr_settings_factory *f){
 static const uint8_t broadcast[6]={255,255,255,255,255,255};
 uint8_t frame[WR_PAIRING_CONFIRM_BYTES];uint32_t request;
 if(wr_pairing_commit_encode(frame,&f->pairing_keys,&f->pairing_state.transcript,WR_PAIRING_WALKMAN))return -1;
 return xnow_client_send(&f->pairing.client,broadcast,frame,sizeof frame,&request);
}
static int pairing_advance_commit(struct wr_settings_factory *f){
 uint32_t request;
 if(f->pairing_commit_pending==PAIR_STORE_RECEIPT_SEEN){
  int rc=xnow_client_pairing_store(&f->pairing.client,1,0,0,&request);
  if(!rc)f->pairing_commit_pending=PAIR_STORE_PUBLISHING;
  return rc==XNOW_CLIENT_PENDING?0:rc;
 }
 if(f->pairing_commit_pending!=PAIR_STORE_WAIT_RECEIPT)return 0;
 unsigned long long now;
 if(hb_monotonic_millis(&now)||now<f->pairing_commit_sent_ms)return -1;
 if(f->pairing_commit_sent_ms&&now-f->pairing_commit_sent_ms<1000)return 0;
 int rc=send_pairing_commit(f);
 if(!rc)f->pairing_commit_sent_ms=now;
 return rc==XNOW_CLIENT_PENDING?0:rc;
}
#ifdef WR_PAIRING_TRACE
static void trace_tuner(uint8_t flags,const uint8_t values[8]){
 xw_player_pairing_trace(12,flags);
 for(unsigned i=0;i<2;i++)if(flags&(2u<<(2*i))){
  uint32_t value=0;
  for(unsigned j=0;j<4;j++)value|=(uint32_t)values[4*i+j]<<(8*j);
  xw_player_pairing_trace(13+i,(int)value);
 }
}
#endif
static void pairing_receive_step(struct wr_settings_factory *f){
 if(!f->pairing.client.used)return;
 int rc=xnow_client_step(&f->pairing.client);
 if(rc<0){(void)wr_settings_factory_pairing_stop(f);return;}
 if(rc){
  if(pairing_advance_commit(f))(void)wr_settings_factory_pairing_stop(f);
  return;
 }
 struct xnow_client_event event;
 uint8_t frame[WR_PAIR_AUTO_FRAME_MAX];
 rc=xnow_client_take(&f->pairing.client,&event,frame,sizeof frame);
 if(rc){(void)wr_settings_factory_pairing_stop(f);return;}
 if(event.kind!=XNOW_CLIENT_RX){
  if(event.result&&!(event.kind==XNOW_CLIENT_TX&&f->pairing_commit_pending==PAIR_STORE_WAIT_RECEIPT))
   (void)wr_settings_factory_pairing_stop(f);
  else if(event.kind==XNOW_CLIENT_ACK&&event.operation==6&&f->pairing_commit_pending==PAIR_STORE_STAGING){
   f->pairing_commit_pending=PAIR_STORE_WAIT_RECEIPT;
   if(pairing_advance_commit(f))(void)wr_settings_factory_pairing_stop(f);
  }else if(event.kind==XNOW_CLIENT_ACK&&event.operation==7&&f->pairing_commit_pending==PAIR_STORE_PUBLISHING){
   f->pairing_saved=1;f->pairing_store_result=0;f->pairing_store_known=1;
   memcpy(f->paired_peer,f->pairing_state.transcript.controller,6);
   (void)wr_settings_factory_pairing_stop(f);
  }
  return;
 }
 unsigned long long now;
 if(hb_monotonic_millis(&now)){(void)wr_settings_factory_pairing_stop(f);return;}
#ifdef WR_PAIRING_TRACE
 int tuner_sample=event.bytes==22&&!memcmp(frame,"WPR3",4);
 int state_sample=event.bytes==38&&!memcmp(frame,"WPR4",4);
 int chip_sample=state_sample||tuner_sample||(event.bytes==13&&!memcmp(frame,"WPR2",4));
 if(!event.flags&&(chip_sample||(event.bytes==9&&!memcmp(frame,"WPR1",4)))&&
    (frame[4]==8||frame[4]==9)&&frame[6]<128&&frame[8]<128&&
    f->pairing_state.phase!=WR_PAIRING_CLOSED&&
    !memcmp(event.address,f->pairing_state.transcript.walkman,6)){
  unsigned queued=frame[5]|((unsigned)frame[6]<<8),dropped=frame[7]|((unsigned)frame[8]<<8);
  uint32_t state[6]={0};
  if(state_sample&&frame[13]==1)
   for(unsigned i=0;i<6;i++)for(unsigned j=0;j<4;j++)state[i]|=(uint32_t)frame[14+i*4+j]<<(8*j);
  xw_player_pairing_trace_radio(frame[4],(int)((dropped<<16)|queued),state_sample&&frame[13]==1?state:0);
  if(chip_sample){
   unsigned seen=frame[9]|((unsigned)frame[10]<<8),eligible=frame[11]|((unsigned)frame[12]<<8);
   int result=seen<=32767&&eligible<=32767?(int)((eligible<<16)|seen):-1;
   xw_player_pairing_trace(frame[4]+2,result);
  }
  if(tuner_sample&&frame[4]==8)trace_tuner(frame[13],frame+14);
  return;
 }
#endif
 int state_ready=event.bytes==43&&!memcmp(frame,"WPL3",4);
 int diagnostic_ready=state_ready||(event.bytes==15&&!memcmp(frame,"WPL2",4));
 if(f->pairing_state.phase==WR_PAIRING_CLOSED&&!event.flags&&
    (diagnostic_ready||(event.bytes==5&&!memcmp(frame,"WPL1",4)))){
  int rc=wr_walkman_pairing_open(&f->pairing_state,event.address,frame[4],now);
#ifdef WR_PAIRING_TRACE
  if(!rc&&diagnostic_ready){
   unsigned flags=frame[14];uint32_t state[6]={0};
   if(state_ready){
    for(unsigned i=0;i<6;i++)for(unsigned j=0;j<4;j++)state[i]|=(uint32_t)frame[15+i*4+j]<<(8*j);
    for(unsigned j=0;j<3;j++)flags|=(unsigned)frame[39+j]<<(8*(j+1));
   }
   xw_player_pairing_trace_radio(15,(int)flags,state_ready&&(frame[14]&128)?state:0);
   trace_tuner(frame[5],frame+6);
  }
#else
  (void)rc;
#endif
 }
 else if(event.flags==XNOW_CLIENT_BROADCAST){
  if(f->pairing_commit_pending==PAIR_STORE_WAIT_RECEIPT&&event.bytes==WR_PAIRING_CONFIRM_BYTES&&
     !memcmp(event.address,f->pairing_state.transcript.controller,6)&&
     !wr_pairing_commit_check(frame,&f->pairing_keys,&f->pairing_state.transcript,WR_PAIRING_CONTROLLER)){
   f->pairing_commit_pending=PAIR_STORE_RECEIPT_SEEN;
   if(pairing_advance_commit(f))(void)wr_settings_factory_pairing_stop(f);
  }else if(event.bytes==WR_PAIR_AUTO_INVITE_BYTES)
   (void)wr_walkman_pair_auto_observe(&f->pairing_state,event.address,frame,event.bytes,now);
  else if(event.bytes==WR_PAIRING_CONFIRM_BYTES)
   (void)wr_walkman_pair_auto_confirm(&f->pairing_state,event.address,frame,event.bytes,&f->pairing_keys,now);
 }
}
int wr_settings_factory_pairing_store_request(struct wr_settings_factory *f,int forget){
 if(!owner(f)||(forget!=0&&forget!=1))return XW_PLAYER_INVALID;
 if((forget&&f->fault_latched)||!f->shared_wifi||xw_player_host_original_exiting()||
    !xw_player_host_wireless_player_active())return XW_PLAYER_UNAVAILABLE;
 if(f->pairing_store_request||f->pairing.owner||f->backend.pending_enabled)return XW_PLAYER_BUSY;
 if(forget){
  unsigned address=0;for(unsigned i=0;i<6;i++)address|=f->paired_peer[i];
  if(f->pairing_store_result||!address||(f->paired_peer[0]&1))return XW_PLAYER_STALE;
 }
 if(forget&&f->held){
  int rc=wr_settings_backend_request_stop(&f->backend);
  if(rc&&rc!=XW_PLAYER_ACCEPTED&&rc!=XW_PLAYER_BUSY)return rc;
 }
 f->pairing_store_request=forget?2:1;
 return XW_PLAYER_ACCEPTED;
}
static void pairing_store_tick(struct wr_settings_factory *f){
 if(!f->pairing_store_request)return;
 unsigned result=2;uint8_t peer[6]={0};
 if(f->pairing_store_job.child){
  int rc=wr_pairing_store_job_poll(&f->pairing_store_job,&result,peer);
  if(rc==XW_PLAYER_BUSY)return;
  if(rc)result=3;
 }else if(!xw_player_host_original_exiting()&&xw_player_host_wireless_player_active()&&
          (f->pairing_store_request==1||(!f->fault_latched&&f->backend.phase!=WR_SETTINGS_FAULT))){
  if(f->pairing_store_request==2&&(f->held||f->backend.phase!=WR_SETTINGS_OFF))return;
  if(wr_pairing_store_job_start(&f->pairing_store_job,f->pairing_store_request==2?f->paired_peer:0)==XW_PLAYER_ACCEPTED)return;
 }
 if(f->pairing_store_request==2&&!result)result=3;
 f->pairing_store_result=result;
 f->pairing_store_known=1;
 if(result)memset(f->paired_peer,0,6);else memcpy(f->paired_peer,peer,6);
 f->pairing_store_request=0;
}
#endif
int wr_settings_factory_use_shared_wifi(struct wr_settings_factory *f){
 if(!owner(f)||!f->forward_owner_view||f->held||f->backend.phase!=WR_SETTINGS_OFF)
  return XW_PLAYER_BUSY;
 f->shared_wifi=1;return 0;
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
#ifdef WR_PAIRING_PROCESS
 pairing_store_tick(f);
#endif
 if(f->owner_view.bound){
  int rc=xw_mode_channel_step(&f->owner_view);
  if(rc&&rc!=XW_MODE_PENDING){
   if(f->held)(void)xw_mode_policy_quiesce(f->owner_view.policy,&f->radio);
   f->fault_latched=1;f->error=XW_PLAYER_UNCERTAIN;(void)wr_settings_backend_request_stop(b);
  }
 }
#ifdef WR_PAIRING_PROCESS
 if(f->pairing.owner){
  if(f->fault_latched||xw_player_host_original_exiting()||!xw_player_host_wireless_player_active())
   (void)wr_settings_factory_pairing_stop(f);
  else pairing_receive_step(f);
  struct xnow_handoff_result receipt;
  int rc=wr_pairing_process_poll(&f->pairing,&receipt);
  if(rc==XW_PLAYER_BUSY)return 0;
#ifdef WR_PAIRING_TRACE
  int result=rc?rc:receipt.startup_failure;
  if(!rc&&(((uint32_t)result&WR_PAIRING_RX_SUMMARY_MASK)==WR_PAIRING_RX_SUMMARY_TAG||
           ((uint32_t)result&WR_PAIRING_RX_SUMMARY_MASK)==WR_PAIRING_RX_TIMED_TAG)){
   xw_player_pairing_trace(16,result);
   result=0;
  }
  xw_player_pairing_trace(7,result);
#endif
  if(rc||release(f)){f->fault_latched=1;return f->error=XW_PLAYER_UNCERTAIN;}
  clear_pairing(f);
  return 0;
 }
#endif
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
#ifdef WR_PAIRING_TRACE
   xw_player_pairing_trace_exit(&b->process);
   uint32_t state[6]={b->phase,(uint32_t)b->error,(uint32_t)b->process.status,
    b->process.service_ready,b->process.radio_ready,(uint32_t)f->error};
   xw_player_pairing_trace_radio(19,b->process.status,state);
#endif
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
#ifdef WR_PAIRING_PROCESS
 if(f->pairing_store_request)return XW_PLAYER_BUSY;
#endif
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
