#include "request.h"
#include <string.h>
static struct xw_request_record *find(struct xw_request_ledger *l,uint64_t id){
 if(!l||!l->session.serial||!id)return 0;
 for(unsigned i=0;i<XW_REQUEST_SLOTS;i++)if(l->records[i].id==id)return &l->records[i];return 0;
}
int xw_requests_init(struct xw_request_ledger *l,struct xw_session_manager *m,struct xw_session_handle h){
 if(!l||l->session.serial)return XW_SESSION_INVALID;struct xw_session_snapshot s;
 int rc=xw_session_read(m,h,&s);if(rc)return rc;if(s.state!=XW_SESSION_ACTIVE)return XW_SESSION_DENIED;
 memset(l,0,sizeof *l);l->session=h;return 0;
}
int xw_request_submit(struct xw_request_ledger *l,struct xw_session_manager *m,uint64_t id,uint32_t capability,const void *payload,uint32_t size){
 if(!l||!id||!payload||!size||size>XW_REQUEST_BYTES)return XW_SESSION_INVALID;
 uint64_t epoch;int rc=xw_session_admit(m,l->session,capability,&epoch);if(rc)return rc;
 struct xw_request_record *r=find(l,id);
 if(r)return r->capability==capability&&r->size==size&&!memcmp(r->payload,payload,size)?XW_REQUEST_DUPLICATE:XW_REQUEST_CONFLICT;
 if(id<=l->highwater)return XW_REQUEST_UNKNOWN;
 r=0;for(unsigned i=0;i<XW_REQUEST_SLOTS;i++){
  struct xw_request_record *p=&l->records[i];
  if(!p->state){r=p;break;}
  if((p->state==XW_REQUEST_DONE||p->state==XW_REQUEST_CANCELLED)&&(!r||p->id<r->id))r=p;
 }
 if(!r)return XW_SESSION_BUSY;
 memset(r,0,sizeof *r);r->id=id;r->epoch=epoch;r->capability=capability;r->size=size;
 memcpy(r->payload,payload,size);r->state=XW_REQUEST_QUEUED;l->highwater=id;return 0;
}
int xw_request_read(const struct xw_request_ledger *l,uint64_t id,struct xw_request_record *out){
 if(!l||!id||!out)return XW_SESSION_INVALID;
 for(unsigned i=0;i<XW_REQUEST_SLOTS;i++)if(l->records[i].id==id){*out=l->records[i];return 0;}
 return XW_REQUEST_UNKNOWN;
}
int xw_request_start(struct xw_request_ledger *l,struct xw_session_manager *m,uint64_t id){
 struct xw_request_record *r=find(l,id);if(!r)return XW_REQUEST_UNKNOWN;
 if(r->state!=XW_REQUEST_QUEUED)return XW_SESSION_DENIED;
 uint64_t epoch;int rc=xw_session_admit(m,l->session,r->capability,&epoch);
 if(rc==XW_SESSION_BUSY)return rc;
 if(rc||epoch!=r->epoch){r->state=XW_REQUEST_CANCELLED;r->result=rc?rc:XW_SESSION_STALE;return r->result;}
 r->state=XW_REQUEST_RUNNING;return 0;
}
int xw_request_finish(struct xw_request_ledger *l,uint64_t id,int32_t result){
 struct xw_request_record *r=find(l,id);if(!r)return XW_REQUEST_UNKNOWN;
 if(r->state!=XW_REQUEST_RUNNING)return XW_SESSION_DENIED;r->result=result;r->state=XW_REQUEST_DONE;return 0;
}
int xw_request_cancel(struct xw_request_ledger *l,uint64_t id){
 struct xw_request_record *r=find(l,id);if(!r)return XW_REQUEST_UNKNOWN;
 if(r->state==XW_REQUEST_RUNNING)return XW_SESSION_PENDING;
 if(r->state==XW_REQUEST_DONE||r->state==XW_REQUEST_CANCELLED)return 0;
 r->state=XW_REQUEST_CANCELLED;return 0;
}
