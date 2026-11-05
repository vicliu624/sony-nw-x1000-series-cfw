#include "native_setting.h"
int xw_wireless_setting_row(int mode){
 switch(mode){case XW_WIRELESS_MODE_WIFI:return 0;case XW_WIRELESS_MODE_OFF:return 1;
 case XW_WIRELESS_MODE_ESPNOW:return 2;default:return -1;}
}
static int state(struct xw_wireless_native_setting *s,struct xw_wireless_mode_snapshot *out){
 return !s||!s->authority?XW_MODE_INVALID:xw_mode_policy_snapshot(s->authority,out);
}
int xw_wireless_setting_open(struct xw_wireless_native_setting *s,struct xw_wireless_mode_policy *authority){
 if(!s||s->authority)return XW_MODE_INVALID;
 struct xw_wireless_mode_snapshot snapshot;int rc=xw_mode_policy_snapshot(authority,&snapshot);if(rc)return rc;
 if(snapshot.phase!=XW_MODE_STABLE||xw_wireless_setting_row(snapshot.selected)<0)return XW_MODE_BUSY;
 s->authority=authority;s->initial=s->preview=snapshot.selected;s->pending=0;return 0;
}
int xw_wireless_setting_select(struct xw_wireless_native_setting *s,unsigned row){
 struct xw_wireless_mode_snapshot snapshot;int rc=state(s,&snapshot);if(rc)return rc;
 if(row>2)return XW_MODE_INVALID;if(s->pending)return XW_MODE_BUSY;
 if(snapshot.phase!=XW_MODE_STABLE||snapshot.selected!=s->initial)return XW_MODE_STALE;
 static const int modes[]={XW_WIRELESS_MODE_WIFI,XW_WIRELESS_MODE_OFF,XW_WIRELESS_MODE_ESPNOW};
 s->preview=modes[row];return 0;
}
int xw_wireless_setting_confirm(struct xw_wireless_native_setting *s){
 struct xw_wireless_mode_snapshot snapshot;int rc=state(s,&snapshot);if(rc)return rc;
 if(s->pending)return XW_MODE_PENDING;
 if(snapshot.phase!=XW_MODE_STABLE||snapshot.selected!=s->initial)return XW_MODE_STALE;
 rc=xw_mode_policy_request(s->authority,s->preview);
 if(rc==XW_MODE_PENDING)s->pending=1;
 else if(!rc)s->initial=s->preview;
 return rc;
}
int xw_wireless_setting_poll(struct xw_wireless_native_setting *s){
 struct xw_wireless_mode_snapshot snapshot;int rc=state(s,&snapshot);if(rc)return rc;
 if(snapshot.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 if(!s->pending)return snapshot.phase==XW_MODE_STABLE&&snapshot.selected==s->initial?0:XW_MODE_STALE;
 if(snapshot.requested!=s->preview)return XW_MODE_STALE;
 if(snapshot.phase!=XW_MODE_STABLE)return XW_MODE_PENDING;
 if(snapshot.selected!=s->preview)return XW_MODE_STALE;
 s->initial=s->preview;s->pending=0;return 0;
}
int xw_wireless_setting_cancel(struct xw_wireless_native_setting *s){
 struct xw_wireless_mode_snapshot snapshot;int rc=state(s,&snapshot);if(rc)return rc;
 /* A committed asynchronous request is no longer a local preview. The native
  * page must report its progress; cancel cannot revive an old draining lease. */
 if(s->pending)return XW_MODE_BUSY;
 s->preview=s->initial;return 0;
}
uint32_t xw_wireless_setting_request(struct xw_wireless_native_setting *s,uint32_t operation,uint32_t row){
 if(operation==5){
  struct xw_wireless_mode_snapshot snapshot;int status=state(s,&snapshot);
  if(status||snapshot.phase!=XW_MODE_STABLE)return 0x574d0000u|((uint32_t)(status?status:XW_MODE_BUSY)&0xffffu);
  int selected=xw_wireless_setting_row(snapshot.selected);
  if(selected<0)return 0x574dffffu;
  s->initial=s->preview=snapshot.selected;s->pending=0;
  return 0x574e0000u|(uint32_t)selected;
 }
 int rc=XW_MODE_INVALID;
 if(row<=2){
  if(operation==2){
   /* A repeated confirm while draining must poll the committed choice rather
    * than attempting to edit the pending preview or starting another drain. */
   if(s&&s->pending){
    rc=xw_wireless_setting_row(s->preview)==(int)row?xw_wireless_setting_poll(s):XW_MODE_BUSY;
   }else{
    rc=xw_wireless_setting_select(s,row);if(!rc)rc=xw_wireless_setting_confirm(s);
   }
  }else if(operation==3)rc=xw_wireless_setting_poll(s);
  else if(operation==4)rc=xw_wireless_setting_cancel(s);
 }
 return 0x574d0000u|((uint32_t)rc&0xffffu);
}
