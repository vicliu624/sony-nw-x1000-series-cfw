#include "parent_trace_observer.h"
#include <errno.h>
#include <string.h>
static int emit(struct xw_parent_trace_observer *o,unsigned stage,const uint32_t values[5]){
 uint32_t payload[12],snapshot[7];
 for(unsigned i=0;i<5;i++)payload[i]=values[i];
 for(unsigned i=0;i<7;i++)payload[i+5]=snapshot[i]=0xffffffffu;
 if(o->snapshot&&!o->snapshot(o->context,snapshot))for(unsigned i=0;i<7;i++)payload[i+5]=snapshot[i];
 return xw_parent_trace_store_record(&o->store,stage,payload);
}
int xw_parent_trace_observer_init(struct xw_parent_trace_observer *o,const struct xw_parent_trace_profile *p,void *context,int (*match)(void *,uintptr_t,unsigned,const unsigned char[32]),int (*owned)(void *),int (*snapshot)(void *,uint32_t[7])){
 int saved=errno,rc=XW_TRACE_INVALID;
 if(!o||!p||!match||!owned||o->initialized||!p->start||!p->bytes||p->bytes>4096||p->start>UINTPTR_MAX-p->bytes)goto done;
 for(unsigned i=0;i<5;i++)if(p->callers[i]<=p->start||p->callers[i]>p->start+p->bytes||(p->callers[i]&3u))goto done;
 rc=xw_parent_trace_store_init(&o->store,p->header,context,owned);
 if(!rc){o->profile=*p;o->context=context;o->match=match;o->snapshot=snapshot;o->initialized=1;}
done:errno=saved;return rc;
}
int xw_parent_trace_observer_call(struct xw_parent_trace_observer *o,uint32_t tag,uintptr_t frame,uintptr_t caller,uintptr_t entry_sp){
 int saved=errno,rc=XW_TRACE_INVALID;unsigned stage=tag&255u;
 if(!o||!o->initialized||(tag&0xffffff00u)!=0x48425000u||!stage||stage>5)goto done;
 if(caller!=o->profile.callers[stage-1]||entry_sp<0x10000u||entry_sp>UINTPTR_MAX-40u||
    (entry_sp&7u)||frame!=entry_sp+8u)goto done;
 if(o->match(o->context,o->profile.start,o->profile.bytes,o->profile.digest)){rc=XW_TRACE_SKIPPED;goto done;}
 /* Only the exact caller/image/entry-SP-qualified capsule owns this frame. */
 uint32_t values[5];const uint32_t *source=(const uint32_t *)frame;
 for(unsigned i=0;i<5;i++)values[i]=source[i];
 rc=emit(o,stage,values);
done:errno=saved;return rc;
}
int xw_parent_trace_observer_event(struct xw_parent_trace_observer *o,unsigned stage,const uint32_t values[5]){
 int saved=errno,rc=XW_TRACE_INVALID;
 if(o&&o->initialized&&values&&stage>5&&stage<=16){
  if(o->match(o->context,o->profile.start,o->profile.bytes,o->profile.digest))rc=XW_TRACE_SKIPPED;
  else rc=emit(o,stage,values);
 }
 errno=saved;return rc;
}
int xw_parent_trace_observer_destroy(struct xw_parent_trace_observer *o){
 int saved=errno,rc=XW_TRACE_INVALID;
 if(o&&o->initialized){rc=xw_parent_trace_store_destroy(&o->store);if(!rc)o->initialized=0;}
 errno=saved;return rc;
}
