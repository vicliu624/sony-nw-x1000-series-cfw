#include "mode_policy.h"
#include <unistd.h>
#include <string.h>
extern unsigned long pthread_self(void);
static int mode_valid(int mode){return mode>=XW_WIRELESS_MODE_OFF&&mode<=XW_WIRELESS_MODE_ESPNOW;}
static int owner(struct xw_wireless_mode_policy *p){
 if(!p||!p->state.phase)return XW_MODE_INVALID;
 return p->owner_pid!=(int)getpid()||p->owner_thread!=pthread_self()?XW_MODE_WRONG_OWNER:0;
}
static void grant(struct xw_wireless_mode_policy *p,int mode,uint64_t consumer,struct xw_wireless_lease *out){
 struct xw_wireless_lease key={p->generation,++p->serial,consumer,mode};
 p->state.lease=key;p->state.active=1;p->state.off_verified=0;*out=key;
}
int xw_mode_policy_init(struct xw_wireless_mode_policy *p,uint64_t generation){
 if(!p||p->state.phase||!generation)return XW_MODE_INVALID;
 memset(p,0,sizeof *p);p->owner_pid=(int)getpid();p->owner_thread=pthread_self();p->generation=generation;
 p->state.selected=p->state.requested=XW_WIRELESS_MODE_UNKNOWN;p->state.phase=XW_MODE_UNVERIFIED;return 0;
}
int xw_mode_policy_confirm_off(struct xw_wireless_mode_policy *p,int mode,int verified){
 int rc=owner(p);if(rc)return rc;if(!mode_valid(mode))return XW_MODE_INVALID;
 if(verified!=1||p->state.active)return XW_MODE_DENIED;
 if(p->state.phase!=XW_MODE_UNVERIFIED&&p->state.phase!=XW_MODE_FAILED)return XW_MODE_INVALID;
 p->state.selected=p->state.requested=mode;p->state.off_verified=1;p->state.phase=XW_MODE_STABLE;return 0;
}
int xw_mode_policy_adopt_wifi(struct xw_wireless_mode_policy *p,uint64_t consumer,int verified,struct xw_wireless_lease *out){
 int rc=owner(p);if(rc)return rc;if(!consumer||!out)return XW_MODE_INVALID;
 if(verified!=1||p->state.phase!=XW_MODE_UNVERIFIED||p->state.active||p->serial==UINT64_MAX)return XW_MODE_DENIED;
 p->state.selected=p->state.requested=XW_WIRELESS_MODE_WIFI;p->state.phase=XW_MODE_STABLE;
 grant(p,XW_WIRELESS_MODE_WIFI,consumer,out);return 0;
}
int xw_mode_policy_request(struct xw_wireless_mode_policy *p,int mode){
 int rc=owner(p);if(rc)return rc;if(!mode_valid(mode))return XW_MODE_INVALID;
 if(p->state.phase==XW_MODE_UNVERIFIED)return XW_MODE_DENIED;
 if(p->state.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 if(p->state.phase==XW_MODE_DRAINING){p->state.requested=mode;return XW_MODE_PENDING;}
 if(p->state.selected==mode)return 0;
 p->state.requested=mode;
 if(p->state.active){p->state.phase=XW_MODE_DRAINING;return XW_MODE_PENDING;}
 if(!p->state.off_verified){p->state.phase=XW_MODE_FAILED;return XW_MODE_FAULT;}
 p->state.selected=mode;return 0;
}
int xw_mode_policy_admitted(struct xw_wireless_mode_policy *p){
 return owner(p)||p->state.phase!=XW_MODE_STABLE?XW_WIRELESS_MODE_UNKNOWN:p->state.selected;
}
int xw_mode_policy_snapshot(struct xw_wireless_mode_policy *p,struct xw_wireless_mode_snapshot *out){
 int rc=owner(p);if(rc)return rc;if(!out)return XW_MODE_INVALID;*out=p->state;return 0;
}
int xw_mode_policy_acquire(struct xw_wireless_mode_policy *p,int mode,uint64_t consumer,struct xw_wireless_lease *out){
 int rc=owner(p);if(rc)return rc;
 if(!out||!consumer||(mode!=XW_WIRELESS_MODE_WIFI&&mode!=XW_WIRELESS_MODE_ESPNOW))return XW_MODE_INVALID;
 if(p->state.phase!=XW_MODE_STABLE||p->state.selected!=mode)return XW_MODE_DENIED;
 if(p->state.active)return XW_MODE_BUSY;
 if(!p->state.off_verified||p->serial==UINT64_MAX)return XW_MODE_DENIED;
 grant(p,mode,consumer,out);return 0;
}
int xw_mode_policy_owns(struct xw_wireless_mode_policy *p,const struct xw_wireless_lease *key){
 int rc=owner(p);if(rc)return rc;if(!key)return XW_MODE_INVALID;
 const struct xw_wireless_lease *held=&p->state.lease;
 return !p->state.active||key->generation!=held->generation||key->serial!=held->serial||
        key->consumer!=held->consumer||key->mode!=held->mode?XW_MODE_STALE:0;
}
int xw_mode_policy_data_allowed(struct xw_wireless_mode_policy *p,const struct xw_wireless_lease *key){
 int rc=xw_mode_policy_owns(p,key);if(rc)return rc;
 return p->state.phase==XW_MODE_STABLE&&p->state.selected==key->mode?0:XW_MODE_DENIED;
}
int xw_mode_policy_quiesce(struct xw_wireless_mode_policy *p,const struct xw_wireless_lease *key){
 int rc=xw_mode_policy_owns(p,key);if(rc)return rc;
 if(p->state.phase==XW_MODE_FAILED)return XW_MODE_FAULT;
 if(p->state.phase==XW_MODE_STABLE){p->state.requested=p->state.selected;p->state.phase=XW_MODE_DRAINING;}
 return XW_MODE_PENDING;
}
int xw_mode_policy_release(struct xw_wireless_mode_policy *p,const struct xw_wireless_lease *key,int verified){
 int rc=xw_mode_policy_owns(p,key);if(rc)return rc;
 if(verified!=1){p->state.phase=XW_MODE_FAILED;return XW_MODE_FAULT;}
 p->state.active=0;p->state.off_verified=1;
 if(p->state.phase==XW_MODE_DRAINING){p->state.selected=p->state.requested;p->state.phase=XW_MODE_STABLE;}
 /* Failed policy stays failed even when a new positive release proves the
  * radio retired. Recovery needs explicit confirm_off, not automatic rearm. */
 return 0;
}
