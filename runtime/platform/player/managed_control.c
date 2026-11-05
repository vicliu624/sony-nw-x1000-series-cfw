#include "managed_control.h"
#include <string.h>
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t get64(const unsigned char *p){return get32(p)|(uint64_t)get32(p+4)<<32;}
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i));}
static void put64(unsigned char *p,uint64_t n){put32(p,(uint32_t)n);put32(p+4,(uint32_t)(n>>32));}
int xw_managed_control_execute(struct xw_managed_player *p,const unsigned char *input,size_t bytes,unsigned char *out,size_t capacity,size_t *used){
 if(!p||!input||!out||!used||bytes!=XW_CONTROL_REQUEST_BYTES||memcmp(input,"XLC1",4)||get32(input+36)||!get64(input+8))return XW_PLAYER_INVALID;
 uint32_t op=get32(input+4),limit=get32(input+32);uint64_t generation=get64(input+16),after=get64(input+24);
 if(op<XW_CONTROL_STATUS||op>XW_CONTROL_PLAY_MODE||op==XW_CONTROL_SNAPSHOT_SYNC||(op==XW_CONTROL_EVENTS?(!limit||limit>XW_EVENT_SLOTS):(after||limit)))return XW_PLAYER_INVALID;
 size_t maximum=op==XW_CONTROL_EVENTS?40+24*limit:op==XW_CONTROL_PLAY_MODE?40:56;
 if(capacity<maximum)return XW_PLAYER_INVALID; /* No side effect before capacity check. */
 unsigned char packet[XW_CONTROL_RESPONSE_MAX]={0};size_t payload=0;int rc;
 if(generation!=p->requests.session.generation)rc=XW_SESSION_STALE;
 else if(op==XW_CONTROL_PLAY_MODE){
  uint32_t native,index;rc=xw_managed_player_mode_get(p,&native,&index);
  if(!rc){put32(packet+24,native);put32(packet+28,index);put64(packet+32,generation);payload=16;}
 }else if(op==XW_CONTROL_EVENTS){
  struct xw_service_event events[XW_EVENT_SLOTS];uint32_t count;uint64_t next;
  rc=xw_managed_player_events(p,generation,after,events,limit,&count,&next);
  if(!rc){put64(packet+24,next);put32(packet+32,count);payload=16+count*24;
   for(uint32_t i=0;i<count;i++){unsigned char *q=packet+40+i*24;put64(q,events[i].sequence);put64(q+8,events[i].epoch);put32(q+16,events[i].kind);put32(q+20,events[i].value);}
  }
 }else{
  rc=op==XW_CONTROL_CLOSE&&p->backend?xw_managed_player_close(p):0;
  struct xw_session_snapshot state;
  if(!rc)rc=xw_session_close_query(p->manager,p->requests.session,&state);
  if(!rc){put32(packet+24,state.state);put32(packet+28,state.grants);put32(packet+32,state.reason);put64(packet+40,state.epoch);put64(packet+48,generation);payload=32;}
 }
 memcpy(packet,"XLR1",4);put32(packet+4,op);put64(packet+8,get64(input+8));put32(packet+16,(uint32_t)rc);put32(packet+20,(uint32_t)payload);
 memcpy(out,packet,24+payload);*used=24+payload;return 0;
}
int xw_managed_sync_execute(struct xw_managed_player *p,const unsigned char *input,size_t bytes,unsigned char *out,size_t capacity,size_t *used,struct xw_rpc_response *scratch){
 if(!p||!input||!out||!used||!scratch||bytes!=40||capacity<1024||memcmp(input,"XLC1",4)||get32(input+4)!=XW_CONTROL_SNAPSHOT_SYNC||!get64(input+8)||get64(input+24)||get32(input+32)||get32(input+36))return XW_PLAYER_INVALID;
 unsigned char packet[1024]={0};size_t payload=0;int rc;
 if(get64(input+16)!=p->requests.session.generation)rc=XW_SESSION_STALE;
 else{
  memset(scratch,0,sizeof *scratch);scratch->kind=XW_RPC_SNAPSHOT;scratch->serial=1;uint64_t sequence;
  rc=xw_managed_player_snapshot_sync(p,&scratch->body.snapshot,&sequence);
  if(!rc){size_t encoded;int code=xw_rpc_encode_response(scratch,packet+32,sizeof packet-32,&encoded);if(code)return code;put64(packet+24,sequence);payload=8+encoded;}
 }
 memcpy(packet,"XLR1",4);put32(packet+4,XW_CONTROL_SNAPSHOT_SYNC);put64(packet+8,get64(input+8));put32(packet+16,(uint32_t)rc);put32(packet+20,(uint32_t)payload);
 memcpy(out,packet,24+payload);*used=24+payload;return 0;
}
