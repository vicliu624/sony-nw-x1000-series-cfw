/* Public owner consumer; RAM-only IPC, no radio/device/volume activation. */
#include <x1000/services/espnow_handoff.h>
#include <x1000/services/espnow_managed_process.h>
#include <x1000/services/espnow_launcher_bridge.h>
#include <x1000/services/espnow_owner_gate.h>
#include <x1000/services/espnow_owner_commands.h>
#include <x1000/services/espnow_owner_stream.h>
#include <x1000/services/espnow_owner_runtime.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned stopped,lookups;
static struct xnow_endpoint *unavailable(void *p){(void)p;lookups++;return 0;}
static void stop(void *p){(void)p;stopped++;}
int main(void){
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_init(&commands,0,unavailable,stop));
 uint8_t request[16]={ 'X','N','C','1',XNOW_OWNER_STOP,0,0,0,1,0,0,0,0,0,0,0 },reply[16];
 memset(reply,0xa5,sizeof reply);assert(xnow_owner_commands_dispatch(&commands,request,16,reply,15)==XNOW_ARGUMENT&&!stopped&&reply[0]==0xa5);
 assert(!xnow_owner_commands_dispatch(&commands,request,16,reply,16)&&stopped==1&&!lookups&&!memcmp(reply,"XNA1",4)&&reply[4]==1&&commands.stopped);
 struct xnow_owner_completion event;assert(xnow_owner_commands_poll(&commands,&event)==XNOW_IDENTITY&&!lookups);
 struct xnow_owner_stream stream;assert(xnow_owner_stream_open(&stream,&commands,-1,-1)==XNOW_ARGUMENT);
 struct xnow_handoff handoff;uint8_t cookie[16]={1,2,3};assert(!xnow_handoff_create(&handoff,cookie));assert(!xnow_handoff_close(&handoff));
 assert(xnow_owner_runtime_init(0,0,0,0,0,-1,cookie,0,0,0)==XNOW_ARGUMENT);
 assert(xnow_launcher_managed_mode(0)==-1);
 puts("Public ESP-NOW owner consumer: bounded commands, stop, RAM pipe lifecycle and invalid-start refusal passed; no radio activation.");return 0;
}
