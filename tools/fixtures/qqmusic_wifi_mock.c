/* Synthetic stock-manager adapter for an actual exec helper test. No WLAN. */
#define _GNU_SOURCE
#include <assert.h>
#include <string.h>
#include <sys/mman.h>
#include <poll.h>
extern char *program_invocation_short_name;
static int initialized;
static struct shared {volatile int powered,prepared,connected,cancelled,inflight;} *state;
int qq_wifi_ipc_guard(void){return strstr(program_invocation_short_name,"guardfail")?-1:0;}
int qq_wifi_route_ready(void){return state&&state->connected;}
int cnmgr_init(void *callback,const void *info){assert(!callback&&!info&&!initialized);state=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);assert(state!=MAP_FAILED);initialized=1;state->connected=strstr(program_invocation_short_name,"already")!=0;return 0;}
int cnmgr_get_state(void){assert(initialized);return state->connected?4:state->powered?3:2;}
int cnmgr_power_on(void){assert(initialized&&!state->powered);state->powered=1;return 0;}
int cnmgr_prepare_connect(void){assert(initialized&&state->powered&&!state->prepared);state->prepared=1;return 0;}
int cnmgr_connect(const void *info){
 assert(!info&&state->prepared&&!state->connected);state->inflight=1;
 if(strstr(program_invocation_short_name,"connectfail")){state->inflight=0;return 73;}
 if(strstr(program_invocation_short_name,"wait")){
  while(!state->cancelled)poll(0,0,10);
  /* Cancel ACK precedes original connect completion by over the old KILL grace. */
  poll(0,0,400);state->inflight=0;return 4;
 }
 if(state->cancelled){state->inflight=0;return 4;}
 state->connected=1;state->inflight=0;return 0;
}
int cnmgr_cancel_connect(void){assert(initialized);state->cancelled=1;return 0;}
int cnmgr_disconnect(void){assert(initialized&&!state->inflight);assert(!strstr(program_invocation_short_name,"already"));state->connected=0;return 0;}
int cnmgr_fin(void){assert(initialized&&!state->inflight);initialized=0;assert(!munmap(state,4096));state=0;return 0;}
