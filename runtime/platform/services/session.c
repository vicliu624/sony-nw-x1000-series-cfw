#include "session.h"
#include <string.h>
static struct xw_session_slot *find(struct xw_session_manager *m,struct xw_session_handle h){
 if(!m||!m->generation||h.generation!=m->generation||!h.serial)return 0;
 for(unsigned i=0;i<XW_SESSION_SLOTS;i++)if(m->slots[i].handle.serial==h.serial)return &m->slots[i];
 return 0;
}
int xw_sessions_init(struct xw_session_manager *m,uint64_t generation,uint32_t supported){
 if(!m||!generation||!supported)return XW_SESSION_INVALID;
 /* Fresh storage only. Reinitializing live state would bypass release. */
 if(m->generation)return XW_SESSION_BUSY;
 memset(m,0,sizeof *m);m->generation=generation;m->supported=supported;m->accepting=1;return 0;
}
int xw_session_open(struct xw_session_manager *m,uint32_t requested,uint32_t authorized,struct xw_session_handle *out){
 if(!m||!m->generation||!out||!requested)return XW_SESSION_INVALID;
 if(m->busy)return XW_SESSION_BUSY;
 if(!m->accepting)return XW_SESSION_DENIED;
 if(requested&~(authorized&m->supported))return XW_SESSION_DENIED;
 if(m->serial==UINT64_MAX)return XW_SESSION_BUSY;
 for(unsigned i=0;i<XW_SESSION_SLOTS;i++){
  struct xw_session_slot *s=&m->slots[i];
  if(s->snapshot.state!=XW_SESSION_EMPTY&&s->snapshot.state!=XW_SESSION_CLOSED)continue;
  memset(s,0,sizeof *s);s->handle.generation=m->generation;s->handle.serial=++m->serial;
  s->snapshot.state=XW_SESSION_ACTIVE;s->snapshot.grants=requested;s->snapshot.epoch=1;*out=s->handle;return 0;
 }
 return XW_SESSION_BUSY;
}
int xw_session_read(struct xw_session_manager *m,struct xw_session_handle h,struct xw_session_snapshot *out){
 if(!out)return XW_SESSION_INVALID;if(m&&m->busy)return XW_SESSION_BUSY;
 struct xw_session_slot *s=find(m,h);if(!s)return XW_SESSION_STALE;*out=s->snapshot;return 0;
}
int xw_session_admit(struct xw_session_manager *m,struct xw_session_handle h,uint32_t capability,uint64_t *epoch){
 if(!epoch||!capability)return XW_SESSION_INVALID;if(m&&m->busy)return XW_SESSION_BUSY;
 struct xw_session_slot *s=find(m,h);if(!s)return XW_SESSION_STALE;
 if(!m->accepting||s->snapshot.state!=XW_SESSION_ACTIVE)return XW_SESSION_DENIED;
 if(capability&~s->snapshot.grants)return XW_SESSION_DENIED;*epoch=s->snapshot.epoch;return 0;
}
int xw_session_revoke(struct xw_session_manager *m,struct xw_session_handle h,uint32_t reason){
 if(reason<XW_SESSION_CLIENT_CLOSE||reason>XW_SESSION_SOURCE_LOST)return XW_SESSION_INVALID;
 if(m&&m->busy)return XW_SESSION_BUSY;struct xw_session_slot *s=find(m,h);if(!s)return XW_SESSION_STALE;
 if(s->snapshot.state==XW_SESSION_FAILED)return XW_SESSION_FAULT;
 if(s->snapshot.state==XW_SESSION_CLOSED)return 0;
 if(s->snapshot.state==XW_SESSION_ACTIVE){s->snapshot.state=XW_SESSION_CLOSING;s->snapshot.grants=0;s->snapshot.reason=reason;s->snapshot.epoch++;}
 return XW_SESSION_PENDING;
}
int xw_session_close_step(struct xw_session_manager *m,struct xw_session_handle h,int (*step)(void *,struct xw_session_handle,uint32_t),void *context){
 if(!step)return XW_SESSION_INVALID;if(m&&m->busy)return XW_SESSION_BUSY;
 struct xw_session_slot *s=find(m,h);if(!s)return XW_SESSION_STALE;
 if(s->snapshot.state==XW_SESSION_CLOSED)return 0;
 if(s->snapshot.state==XW_SESSION_FAILED)return XW_SESSION_FAULT;
 if(s->snapshot.state!=XW_SESSION_CLOSING)return XW_SESSION_DENIED;
 m->busy=1;int rc=step(context,h,s->snapshot.reason);m->busy=0;
 if(!rc){s->snapshot.state=XW_SESSION_CLOSED;m->receipts[m->receipt_next]=*s;m->receipt_next=(m->receipt_next+1)%XW_SESSION_SLOTS;return 0;}
 if(rc==XW_SESSION_PENDING)return rc;
 s->snapshot.state=XW_SESSION_FAILED;return XW_SESSION_FAULT;
}
int xw_session_close_query(struct xw_session_manager *m,struct xw_session_handle h,struct xw_session_snapshot *out){
 if(!m||!out||!h.serial)return XW_SESSION_INVALID;
 if(m->busy)return XW_SESSION_BUSY;
 if(h.generation!=m->generation)return XW_SESSION_STALE;
 struct xw_session_slot *s=find(m,h);
 if(s){*out=s->snapshot;return 0;}
 for(unsigned i=0;i<XW_SESSION_SLOTS;i++)if(m->receipts[i].handle.serial==h.serial){*out=m->receipts[i].snapshot;return 0;}
 return XW_SESSION_STALE;
}
int xw_sessions_drained(struct xw_session_manager *m){
 if(!m||!m->generation)return XW_SESSION_INVALID;if(m->busy)return XW_SESSION_BUSY;
 if(m->accepting)return XW_SESSION_DENIED;
 unsigned pending=0;
 for(unsigned i=0;i<XW_SESSION_SLOTS;i++){
  uint32_t state=m->slots[i].snapshot.state;if(state==XW_SESSION_FAILED)return XW_SESSION_FAULT;
  if(state!=XW_SESSION_EMPTY&&state!=XW_SESSION_CLOSED)pending=1;
 }
 return pending?XW_SESSION_PENDING:0;
}
int xw_sessions_stop_admission(struct xw_session_manager *m){
 if(!m||!m->generation)return XW_SESSION_INVALID;if(m->busy)return XW_SESSION_BUSY;
 m->accepting=0;return 0;
}
int xw_sessions_quiesce(struct xw_session_manager *m,uint32_t reason){
 if(!m||!m->generation||reason<XW_SESSION_CLIENT_CLOSE||reason>XW_SESSION_SOURCE_LOST)return XW_SESSION_INVALID;
 if(m->busy)return XW_SESSION_BUSY;m->accepting=0;
 for(unsigned i=0;i<XW_SESSION_SLOTS;i++)if(m->slots[i].snapshot.state==XW_SESSION_ACTIVE)xw_session_revoke(m,m->slots[i].handle,reason);
 return xw_sessions_drained(m);
}
int xw_sessions_resume(struct xw_session_manager *m){
 if(!m||!m->generation)return XW_SESSION_INVALID;if(m->busy)return XW_SESSION_BUSY;
 if(m->accepting)return 0;int rc=xw_sessions_drained(m);if(rc)return rc;m->accepting=1;return 0;
}
