#include "../../runtime/platform/player/managed_control.h"
#include "../../runtime/platform/player/managed_codec.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static int snapshot(void *c,struct xw_player_snapshot *s){(void)c;s->valid=XW_PF_STATE;s->state=XW_PLAY_PLAYING;return 0;}
static int close_backend(void *c){(void)c;assert(0);return 0;}
static unsigned mode_reads;
static int mode_read(void *c,uint32_t *raw,uint32_t *index){(void)c;mode_reads++;*raw=5;*index=4;return 0;}
int main(void){
 static struct xw_session_manager m;static struct xw_player backend;static struct xw_managed_player p;
 struct xw_session_handle h;struct xw_player_provider provider={XW_PLAYER_API,0,0,snapshot,0,0,close_backend};
 assert(!xw_sessions_init(&m,7,1)&&!xw_session_open(&m,1,1,&h)&&!xw_player_bind(&backend,&provider)&&!xw_managed_player_bind(&p,&m,h,&backend));
 unsigned char request[40]={ 'X','L','C','1',1,0,0,0,1,0,0,0,0,0,0,0,7 },out[432],old[432];size_t size=99;
 assert(!xw_managed_control_execute(&p,request,40,out,sizeof out,&size)&&size==56&&!memcmp(out,"XLR1",4)&&out[24]==XW_SESSION_ACTIVE);
 struct xw_session_snapshot status;assert(!xw_control_status_decode(out,size,1,1,7,&status)&&status.state==XW_SESSION_ACTIVE);
 assert(!xw_managed_player_refresh(&p));request[4]=2;request[32]=16;
 assert(!xw_managed_control_execute(&p,request,40,out,sizeof out,&size)&&out[32]==1&&size==64);
 struct xw_service_event rows[16],saved[16];uint32_t count;uint64_t next;
 assert(!xw_control_events_decode(out,size,1,0,16,rows,16,&count,&next)&&count==1&&next==1);
 memcpy(saved,rows,sizeof rows);out[40]=2;count=99;next=99;
 assert(xw_control_events_decode(out,size,1,0,16,rows,16,&count,&next)==XW_PLAYER_PROTOCOL&&count==99&&next==99&&!memcmp(rows,saved,sizeof rows));
 assert(!xw_control_request_encode(4,1,7,0,0,request,sizeof request));
 static unsigned char sync[1024];static struct xw_rpc_response scratch,decoded;
 request[4]=4;request[32]=0;
 assert(!xw_managed_sync_execute(&p,request,40,sync,sizeof sync,&size,&scratch));
 assert(sync[24]==1&&!xw_rpc_decode_response(sync+32,size-32,&decoded)&&decoded.body.snapshot.state==XW_PLAY_PLAYING);
 struct xw_player_snapshot observation,prior;uint64_t sequence;
 assert(!xw_control_sync_decode(sync,size,1,&observation,&sequence,&decoded)&&sequence==1&&observation.state==XW_PLAY_PLAYING);
 prior=observation;sequence=99;sync[56]=0x80; /* unknown valid-field bit */
 assert(xw_control_sync_decode(sync,size,1,&observation,&sequence,&decoded)==XW_PLAYER_PROTOCOL&&sequence==99&&!memcmp(&prior,&observation,sizeof prior));
 sync[56]=XW_PF_STATE;
 assert(xw_control_sync_decode(sync,size,2,&observation,&sequence,&decoded)==XW_PLAYER_PROTOCOL&&sequence==99);
 request[4]=3;request[32]=0;memset(out,0xa5,sizeof out);memcpy(old,out,sizeof out);size=99;
 assert(!xw_managed_player_mode_bind(&p,0,mode_read));
 assert(!xw_control_request_encode(XW_CONTROL_PLAY_MODE,10,7,0,0,request,sizeof request));
 assert(xw_managed_control_execute(&p,request,40,out,39,&size)==XW_PLAYER_INVALID&&!mode_reads);
 assert(!xw_managed_control_execute(&p,request,40,out,sizeof out,&size)&&size==40&&mode_reads==1);
 uint32_t raw=99,index=99;assert(!xw_control_mode_decode(out,size,10,7,&raw,&index)&&raw==5&&index==4);
 raw=index=99;out[24]=4;assert(xw_control_mode_decode(out,size,10,7,&raw,&index)==XW_PLAYER_PROTOCOL&&raw==99&&index==99);
 assert(xw_control_mode_decode(out,size,11,7,&raw,&index)==XW_PLAYER_PROTOCOL);
 assert(!xw_control_request_encode(XW_CONTROL_CLOSE,1,7,0,0,request,sizeof request));
 memset(out,0xa5,sizeof out);memcpy(old,out,sizeof out);size=99;
 assert(xw_managed_control_execute(&p,request,40,out,24,&size)==XW_PLAYER_INVALID&&size==99&&!memcmp(out,old,sizeof out)&&p.backend);
 assert(!xw_managed_control_execute(&p,request,40,out,sizeof out,&size)&&out[24]==XW_SESSION_CLOSED&&backend.initialized);
 assert(!xw_managed_control_execute(&p,request,40,out,sizeof out,&size)&&out[24]==XW_SESSION_CLOSED);
 request[36]=1;assert(xw_managed_control_execute(&p,request,40,out,sizeof out,&size)==XW_PLAYER_INVALID);
 puts("Control framing: status, events, close receipt, capacity-before-side-effect and reserved-field refusal passed");return 0;
}
