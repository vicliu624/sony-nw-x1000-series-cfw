#include "native_owner.h"
static int state(struct xw_native_wireless_owner *n,struct xw_wireless_mode_snapshot *s){
 return !n||!n->policy?XW_MODE_INVALID:xw_mode_policy_snapshot(n->policy,s);
}
static int fail(struct xw_native_wireless_owner *n){
 n->fault=1;
 if(n->held)(void)xw_mode_policy_release(n->policy,&n->lease,0);
 return XW_MODE_FAULT;
}
int xw_native_wireless_bind(struct xw_native_wireless_owner *n,struct xw_wireless_mode_policy *p,uint64_t consumer,void *context,int (*enqueue)(void *,const uint32_t[4]),int (*stop)(void *,const struct xw_wireless_lease *),int (*retirement)(void *,const struct xw_wireless_lease *)){
 if(!n||n->policy||!consumer||!enqueue||!stop||!retirement)return XW_MODE_INVALID;
 struct xw_wireless_mode_snapshot s;int rc=xw_mode_policy_snapshot(p,&s);if(rc)return rc;
 n->policy=p;n->consumer=consumer;n->context=context;n->enqueue=enqueue;n->stop=stop;n->retirement=retirement;
 n->held=n->stopping=n->fault=0;return 0;
}
int xw_native_wireless_submit(struct xw_native_wireless_owner *n,const uint32_t message[4]){
 struct xw_wireless_mode_snapshot s;int rc=state(n,&s);if(rc)return rc;
 if(!message)return XW_MODE_INVALID;if(n->fault)return XW_MODE_FAULT;
 if(n->stopping||s.phase!=XW_MODE_STABLE||s.selected!=XW_WIRELESS_MODE_WIFI)return XW_MODE_DENIED;
 if(!n->held){
  rc=xw_mode_policy_acquire(n->policy,XW_WIRELESS_MODE_WIFI,n->consumer,&n->lease);if(rc)return rc;n->held=1;
 }
 rc=xw_mode_policy_data_allowed(n->policy,&n->lease);if(rc)return rc;
 /* No deferred payload copy: original enqueue retains its original lifetime
  * contract. A failed enqueue cannot establish that the hardware is off. */
 if(n->enqueue(n->context,message))return fail(n);
 return 0;
}
int xw_native_wireless_adopt(struct xw_native_wireless_owner *n,const struct xw_wireless_lease *lease){
 struct xw_wireless_mode_snapshot s;int rc=state(n,&s);if(rc)return rc;
 if(!lease||n->held||n->fault||n->stopping||lease->consumer!=n->consumer||lease->mode!=XW_WIRELESS_MODE_WIFI)return XW_MODE_INVALID;
 rc=xw_mode_policy_data_allowed(n->policy,lease);if(rc)return rc;
 n->lease=*lease;n->held=1;return 0;
}
int xw_native_wireless_stop(struct xw_native_wireless_owner *n){
 struct xw_wireless_mode_snapshot s;int rc=state(n,&s);if(rc)return rc;
 if(n->fault)return XW_MODE_FAULT;if(!n->held)return 0;
 if(n->stopping)return XW_MODE_PENDING;
 rc=xw_mode_policy_quiesce(n->policy,&n->lease);if(rc!=0&&rc!=XW_MODE_PENDING)return rc;
 n->stopping=1;
 if(n->stop(n->context,&n->lease))return fail(n);
 return XW_MODE_PENDING;
}
int xw_native_wireless_poll(struct xw_native_wireless_owner *n){
 struct xw_wireless_mode_snapshot s;int rc=state(n,&s);if(rc)return rc;
 if(n->fault)return XW_MODE_FAULT;if(!n->held)return 0;
 if(s.phase==XW_MODE_FAILED)return fail(n);
 if(s.phase==XW_MODE_DRAINING&&!n->stopping)return xw_native_wireless_stop(n);
 if(!n->stopping)return 0;
 rc=n->retirement(n->context,&n->lease);
 if(rc==XW_MODE_PENDING)return rc;
 if(rc)return fail(n);
 rc=xw_mode_policy_release(n->policy,&n->lease,1);if(rc)return fail(n);
 n->held=n->stopping=0;return 0;
}
