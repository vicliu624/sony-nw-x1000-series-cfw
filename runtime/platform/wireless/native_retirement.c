#include "native_retirement.h"
#include "native_rf_worker.h"
#include "native_delivery.h"
#include "native_boot.h"
#include "mode_channel.h"
#include <string.h>
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(i*8));}
static uint32_t get32(const unsigned char *p){uint32_t n=0;for(unsigned i=0;i<4;i++)n|=(uint32_t)p[i]<<(i*8);return n;}
static void put64(unsigned char *p,uint64_t n){put32(p,(uint32_t)n);put32(p+4,(uint32_t)(n>>32));}
static uint64_t get64(const unsigned char *p){return get32(p)|(uint64_t)get32(p+4)<<32;}
static int valid(const struct xw_native_retirement *r){
 return r&&r->lease.generation&&r->lease.serial&&r->lease.consumer&&r->lease.mode==XW_WIRELESS_MODE_WIFI&&
  r->modules_clear<=1&&r->sealed<=1&&(!r->sealed||(r->native_result==0&&r->public_state==2&&r->modules_clear==1))&&
  (r->phase==XW_MODE_DRAINING||r->phase==XW_MODE_FAILED)&&
  (r->kind==XW_NATIVE_RETIRE_OFF_CALL||(r->kind==XW_NATIVE_RETIRE_DISABLE_CHECKPOINT&&r->native_result==0));
}
int xw_native_retirement_encode(unsigned char raw[64],const struct xw_native_retirement *r){
 if(!raw||!valid(r))return XW_MODE_INVALID;
 memset(raw,0,64);memcpy(raw,"WRO1",4);put32(raw+4,1);put64(raw+8,r->lease.generation);put64(raw+16,r->lease.serial);put64(raw+24,r->lease.consumer);
 put32(raw+32,r->lease.mode);put32(raw+36,(uint32_t)r->native_result);put32(raw+40,(uint32_t)r->public_state);put32(raw+44,r->phase);put32(raw+48,r->modules_clear);put32(raw+52,r->sealed);put32(raw+56,r->kind);return 0;
}
int xw_native_retirement_decode(struct xw_native_retirement *out,const unsigned char *raw,unsigned bytes){
 if(!out||!raw||bytes!=64||memcmp(raw,"WRO1",4)||get32(raw+4)!=1)return XW_MODE_INVALID;
 for(unsigned i=60;i<64;i++)if(raw[i])return XW_MODE_INVALID;
 struct xw_native_retirement r={{get64(raw+8),get64(raw+16),get64(raw+24),(int32_t)get32(raw+32)},(int32_t)get32(raw+36),(int32_t)get32(raw+40),get32(raw+44),get32(raw+48),get32(raw+52),get32(raw+56)};
 if(!valid(&r))return XW_MODE_INVALID;*out=r;return 0;
}
static int note(int native_result,unsigned kind){
 struct xw_native_retirement cached;
 if(!xw_native_rf_worker_retirement(&cached)){
  if(!xw_native_rf_worker_notice_pending())return 0;
  unsigned char repeat[64];int encoded=xw_native_retirement_encode(repeat,&cached);
  int sent=encoded?encoded:xw_native_delivery_send_notice(repeat);
  if(!sent)xw_native_rf_worker_notice_sent(&cached.lease);return sent;
 }
 struct xw_mode_reply view;int rc=xw_native_rf_worker_observe(&view);if(rc)return rc;
 /* A fresh drain/failed view cannot become data-allowed again at this key.
  * Stable scan completions are deliberately not retirement evidence. */
 if(view.phase!=XW_MODE_DRAINING&&view.phase!=XW_MODE_FAILED)return 0;
 struct xw_native_retirement receipt={view.lease,native_result,-1,view.phase,0,0,kind};
 if(!native_result){
  receipt.public_state=xw_native_boot_manager_state();
  if(receipt.public_state==2)receipt.modules_clear=xw_native_boot_radio_unloaded()==1;
 }
 if(!receipt.native_result&&receipt.public_state==2&&receipt.modules_clear==1){
  receipt.sealed=1;rc=xw_native_rf_worker_seal(&receipt);if(rc)return rc;
 }
 unsigned char raw[64];rc=xw_native_retirement_encode(raw,&receipt);
 int sent=rc?rc:xw_native_delivery_send_notice(raw);
 if(!sent&&receipt.sealed)xw_native_rf_worker_notice_sent(&receipt.lease);return sent;
}
int xw_native_rf_poweroff_note(int native_result){return note(native_result,XW_NATIVE_RETIRE_OFF_CALL);}
int xw_native_rf_disable_checkpoint(uint32_t event){
 if(event!=0x4c0006u)return 0;
 int rc=xw_native_rf_refresh_offer();
 if(rc!=0&&rc!=XW_MODE_PENDING&&rc!=XW_NATIVE_RF_CLEANUP_VIEW)return rc;
 return note(0,XW_NATIVE_RETIRE_DISABLE_CHECKPOINT);
}
