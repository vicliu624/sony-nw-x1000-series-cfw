#include "managed_codec.h"
#include "snapshot.h"
#include <string.h>
static uint32_t u32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t u64(const unsigned char *p){return u32(p)|(uint64_t)u32(p+4)<<32;}
static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(i*8));}
static void put64(unsigned char *p,uint64_t v){put32(p,(uint32_t)v);put32(p+4,(uint32_t)(v>>32));}
static int header(const unsigned char *p,size_t n,uint32_t op,uint64_t correlation){
 if(!p||n<24||!correlation||memcmp(p,"XLR1",4)||u32(p+4)!=op||u64(p+8)!=correlation||u32(p+20)!=n-24)return XW_PLAYER_PROTOCOL;
 int32_t rc;uint32_t raw=u32(p+16);memcpy(&rc,&raw,4);
 if(rc>0||rc<XW_PLAYER_UNCERTAIN||(rc&&n!=24))return XW_PLAYER_PROTOCOL;return rc;
}
int xw_control_request_encode(uint32_t op,uint64_t correlation,uint64_t generation,uint64_t after,uint32_t limit,unsigned char *out,size_t capacity){
 if(!out||capacity<40||!correlation||!generation||op<1||op>XW_CONTROL_PLAY_MODE||(op==XW_CONTROL_EVENTS?(!limit||limit>XW_EVENT_SLOTS):(after||limit)))return XW_PLAYER_INVALID;
 unsigned char frame[40]={0};memcpy(frame,"XLC1",4);put32(frame+4,op);put64(frame+8,correlation);put64(frame+16,generation);put64(frame+24,after);put32(frame+32,limit);memcpy(out,frame,40);return 0;
}
int xw_control_status_decode(const unsigned char *p,size_t n,uint32_t op,uint64_t correlation,uint64_t generation,struct xw_session_snapshot *out){
 if(!out||!generation||(op!=XW_CONTROL_STATUS&&op!=XW_CONTROL_CLOSE))return XW_PLAYER_INVALID;
 int rc=header(p,n,op,correlation);if(rc)return rc;
 if(n!=56||u32(p+36)||u64(p+48)!=generation)return XW_PLAYER_PROTOCOL;
 struct xw_session_snapshot s={0};s.state=u32(p+24);s.grants=u32(p+28);s.reason=u32(p+32);s.epoch=u64(p+40);
 if(s.state<XW_SESSION_ACTIVE||s.state>XW_SESSION_FAILED||!s.epoch||s.reason>XW_SESSION_SOURCE_LOST||(s.state!=XW_SESSION_ACTIVE&&s.grants)||(op==XW_CONTROL_CLOSE&&s.state!=XW_SESSION_CLOSED))return XW_PLAYER_PROTOCOL;
 *out=s;return 0;
}
int xw_control_mode_decode(const unsigned char *p,size_t n,uint64_t correlation,uint64_t generation,uint32_t *native,uint32_t *index){
 if(!native||!index||native==index||!generation)return XW_PLAYER_INVALID;
 int rc=header(p,n,XW_CONTROL_PLAY_MODE,correlation);if(rc)return rc;
 if(n!=40||u64(p+32)!=generation)return XW_PLAYER_PROTOCOL;
 uint32_t raw=u32(p+24),menu=u32(p+28);
 if(!((raw<=3&&menu==raw)||(raw==5&&menu==4)))return XW_PLAYER_PROTOCOL;
 *native=raw;*index=menu;return 0;
}
int xw_control_events_decode(const unsigned char *p,size_t n,uint64_t correlation,uint64_t after,uint32_t limit,struct xw_service_event *out,uint32_t capacity,uint32_t *count,uint64_t *next){
 if(!out||!count||!next||!limit||limit>XW_EVENT_SLOTS||capacity<limit)return XW_PLAYER_INVALID;
 int rc=header(p,n,XW_CONTROL_EVENTS,correlation);if(rc)return rc;
 if(n<40||u32(p+36))return XW_PLAYER_PROTOCOL;
 uint32_t k=u32(p+32);if(k>limit||n!=40+(size_t)k*24||after>UINT64_MAX-k||u64(p+24)!=after+k)return XW_PLAYER_PROTOCOL;
 struct xw_service_event staged[XW_EVENT_SLOTS];
 for(uint32_t i=0;i<k;i++){
  const unsigned char *q=p+40+i*24;staged[i].sequence=u64(q);staged[i].epoch=u64(q+8);staged[i].kind=u32(q+16);staged[i].value=u32(q+20);
  if(staged[i].sequence!=after+i+1||!staged[i].epoch||!staged[i].kind)return XW_PLAYER_PROTOCOL;
 }
 memcpy(out,staged,k*sizeof *out);*count=k;*next=after+k;return 0;
}
int xw_control_sync_decode(const unsigned char *p,size_t n,uint64_t correlation,struct xw_player_snapshot *out,uint64_t *sequence,struct xw_rpc_response *scratch){
 if(!out||!sequence||!scratch)return XW_PLAYER_INVALID;
 int rc=header(p,n,XW_CONTROL_SNAPSHOT_SYNC,correlation);if(rc)return rc;
 if(n<56)return XW_PLAYER_PROTOCOL;
 rc=xw_rpc_decode_response(p+32,n-32,scratch);if(rc)return rc;
 if(scratch->kind!=XW_RPC_SNAPSHOT||scratch->serial!=1||scratch->result)return XW_PLAYER_PROTOCOL;
 struct xw_player_snapshot value;rc=xw_player_snapshot_validate(&scratch->body.snapshot,&value);if(rc)return rc;
 *out=value;*sequence=u64(p+24);return 0;
}
