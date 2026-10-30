#include "runner.h"
#include "../../platform/espnow/xnow_endpoint_security.h"
#include "../../native/sha256.h"
#include <string.h>
static const unsigned sizes[]={0,1,249,250,0,1,250,251,1469,1470};
static void event(struct probe_run *r,const char *name,int value){if(r->log.event(r->log.context,name,value))r->log_failed=1;}
static void stop(struct probe_run *r,int failure){if(failure&&!r->failure)r->failure=failure;if(!r->stopping){r->stopping=1;event(r,"stop-request",failure);xnow_full_control_stop(r->control);}}
int probe_init(struct probe_run *r,struct xnow_full_control *c,const struct probe_log *log,const uint8_t peer[6],unsigned tx,unsigned seconds){
 if(!r||!c||!c->initialized||c->session.phase!=XNOW_SESSION_STARTING||c->manager.held||!log||!log->event||!log->frame||!peer||tx>1||seconds<1||seconds>120)return -1;
 unsigned any=0;for(unsigned i=0;i<6;i++)any|=peer[i];if(!any||(peer[0]&1))return -1;
 memset(r,0,sizeof(*r));r->control=c;r->log=*log;memcpy(r->peer,peer,6);r->tx=tx;r->window=seconds*1000u;r->prior=-1;return 0;
}
int probe_use_security(struct probe_run *r,const uint8_t lmk[16],void *context,int (*prepare)(void *,struct xnow_full_control *)){
 if(!r||!r->control||r->started||!lmk||!prepare)return -1;
 r->encrypted=1;memcpy(r->api_lmk,lmk,16);r->prepare_context=context;r->prepare=prepare;return 0;
}
int probe_step(struct probe_run *r,uint32_t now,unsigned requested){
 if(!r||!r->control)return PROBE_UNCERTAIN;
 struct xnow_full_control *c=r->control;
 if(!r->started){r->started=1;r->began=r->last=now;event(r,"run-version",1);event(r,"mode-tx",(int)r->tx);if(r->log_failed)stop(r,-1);}
 if((uint32_t)(now-r->last)>0x7fffffffu)stop(r,-2);
 r->last=now;
 if(requested)stop(r,1);
 /* Deadline requests recovery; it never kills an in-flight Sony operation. */
 if(!r->stopping&&(uint32_t)(now-r->began)>=r->window)stop(r,r->ready&&!r->tx?0:2);
 int action=c->job.pid?c->job.action:c->session.pending?c->session.pending:c->session.next;
 if(action!=r->prior){event(r,"action",action);r->prior=action;}
 if(r->log_failed&&!r->stopping)stop(r,-3);
 int phase=xnow_full_control_step(c);
 if(phase<0){event(r,"ownership-uncertain",phase);return PROBE_UNCERTAIN;}
 if(phase==XNOW_SESSION_REPAIR_REQUIRED){event(r,"repair-required",c->session.restore_failure);return PROBE_REPAIR;}
 if(xnow_full_control_finished(c)){
  if(!r->failure&&(r->log_failed||c->session.failure||c->session.restore_failure||(r->tx?(r->completions!=10||r->mac_failures):r->encrypted?!r->received:!r->captured)))r->failure=3;
  event(r,"tx-completions",(int)r->completions);event(r,"mac-failures",(int)r->mac_failures);event(r,"rx-frames",(int)r->received);
  event(r,"startup-failure",c->session.failure);event(r,"restore-failure",c->session.restore_failure);
  event(r,"done",r->failure||r->log_failed||c->session.failure||c->session.restore_failure?1:0);volatile uint8_t *secret=r->api_lmk;for(unsigned i=0;i<16;i++)secret[i]=0;return PROBE_DONE;
 }
 if(phase!=XNOW_SESSION_READY||r->stopping)return PROBE_RUNNING;
 struct xnow_endpoint *e=xnow_full_control_endpoint(c);if(!e){stop(r,-4);return PROBE_RUNNING;}
 if(!r->ready){
  r->ready=1;r->ready_at=now;event(r,"radio-ready",0);
  if(r->encrypted){int result=r->prepare(r->prepare_context,c);event(r,"security-prepare",result);if(result){stop(r,result);return PROBE_RUNNING;}
   if(!r->tx){struct xnow_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,r->peer,6);memcpy(peer.lmk,r->api_lmk,16);peer.version=2;peer.encrypt=1;result=xnow_endpoint_add(e,&peer);memset(peer.lmk,0,16);if(result){stop(r,result);return PROBE_RUNNING;}r->added=1;}
  }
 }
 if(r->log_failed){stop(r,-3);return PROBE_RUNNING;}
 uint8_t frame[XNOW_ESPNOW_ACTION_MAX+16u];size_t bytes=0;int received;
 if(r->encrypted){struct xnow_full_received info;received=xnow_endpoint_receive(e,frame,sizeof frame,&info);
  if(!received&&memcmp(info.source,r->peer,6)==0&&(info.flags&XNOW_RX_AUTHENTICATED)){r->received++;event(r,"authenticated-rx-bytes",(int)info.info.payload_bytes);
   if(!r->captured){struct hb_sha256 hash;uint8_t digest[32];hb_sha256_init(&hash);hb_sha256_update(&hash,frame,info.info.payload_bytes);hb_sha256_final(&hash,digest);for(unsigned i=0;i<8;i++){char name[]="rx-sha0";name[6]=(char)('0'+i);uint32_t word=(uint32_t)digest[i*4]|((uint32_t)digest[i*4+1]<<8)|((uint32_t)digest[i*4+2]<<16)|((uint32_t)digest[i*4+3]<<24);event(r,name,(int)word);}r->captured=1;}
  }
  if(received==XNOW_SECURITY_AUTH||received==XNOW_SECURITY_REPLAY||received==XNOW_SECURITY_FORMAT||received==XNOW_ENDPOINT_CRYPTO_UNAVAILABLE){event(r,"rx-rejected",received);received=XNOW_AGAIN;}
 }else{received=xnow_full_receive_action(&c->backend,c->local_mac,frame,sizeof frame,&bytes);
  if(!received){if(!memcmp(frame+10,r->peer,6)){r->received++;if(!r->captured&&(frame[1]&0x40)){if(r->log.frame(r->log.context,frame,bytes))r->log_failed=1;else r->captured=1;}}}
 }
 if(received&&received!=XNOW_AGAIN){stop(r,received);return PROBE_RUNNING;}
 if(r->log_failed){stop(r,-3);return PROBE_RUNNING;}
 if(r->tx&&r->index<sizeof sizes/sizeof sizes[0]){
  if(!r->queued){
   struct xnow_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,r->peer,6);peer.version=r->index<4?1:2;
   if(r->encrypted){peer.encrypt=1;memcpy(peer.lmk,r->api_lmk,16);}
   int result=r->added?xnow_endpoint_modify(e,&peer):xnow_endpoint_add(e,&peer);
   volatile uint8_t *secret=peer.lmk;for(unsigned i=0;i<16;i++)secret[i]=0;
   if(result){stop(r,result);return PROBE_RUNNING;}r->added=1;
   uint8_t payload[1470];for(unsigned i=0;i<sizes[r->index];i++)payload[i]=(uint8_t)(i*17u+r->index);
   result=xnow_endpoint_send(e,r->peer,payload,sizes[r->index]);
   if(result){stop(r,result);return PROBE_RUNNING;}r->queued=1;event(r,"tx-case",(int)r->index);
  }
  struct xnow_endpoint_result result;int polled=xnow_endpoint_poll(e,&result);
  if(!polled){r->completions++;if(result.result||result.stock_status)r->mac_failures++;event(r,"tx-result",result.result?result.result:(int)result.stock_status);r->index++;r->queued=0;}
  else if(polled!=XNOW_PENDING){stop(r,polled);return PROBE_RUNNING;}
 }
 if(r->tx&&r->index==sizeof sizes/sizeof sizes[0])stop(r,0);
 if(r->log_failed)stop(r,-3);
 return PROBE_RUNNING;
}
