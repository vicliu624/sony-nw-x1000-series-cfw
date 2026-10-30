#ifndef XNOW_OWNER_COMMANDS_H
#define XNOW_OWNER_COMMANDS_H
#include "xnow_endpoint.h"
/* Experimental full-owner command boundary, distinct from legacy chat IPC.
 * Caller frames pipe reads, authenticates its inherited endpoint and wipes
 * input (ADD/MODIFY carries LMK). All calls serialized by the owner process.
 * endpoint() must use full_control_endpoint(), including current lease checks.
 * stop() must request full_control_stop(); its return is NOT restore completion.
 * This component does not load images, claim USB ownership or manage PN files. */
enum {XNOW_OWNER_ADD=1,XNOW_OWNER_MODIFY=2,XNOW_OWNER_DELETE=3,
      XNOW_OWNER_SEND=4,XNOW_OWNER_STOP=5};
#define XNOW_OWNER_HEADER 16u
#define XNOW_OWNER_COMMAND_MAX (XNOW_OWNER_HEADER+6u+XNOW_ESPNOW_V2_MAX)
struct xnow_owner_commands {
 void *context;struct xnow_endpoint *(*endpoint)(void *);void (*stop)(void *);
 uint32_t send_token;int sending,stopped;
};
struct xnow_owner_completion {uint32_t request;struct xnow_endpoint_result result;};
struct xnow_full_control;
#ifdef __cplusplus
extern "C" {
#endif
int xnow_owner_commands_init(struct xnow_owner_commands *,void *,struct xnow_endpoint *(*)(void *),void (*)(void *));
/* Actual controller binding; no direct endpoint pointer bypass. Controller must
 * outlive this object. Initialization alone does not start/load the radio. */
int xnow_owner_commands_control(struct xnow_owner_commands *,struct xnow_full_control *);
/* Request: XNC1,op:u8,flags:u8,reserved:u16,token:u32LE,bodybytes:u32LE.
 * Nonzero token. All flags zero except SEND bit0 means all registered peers.
 * ADD/MODIFY body=MAC6,channel,version,encrypt,reserved0,LMK16 (26 bytes).
 * DELETE body=MAC6. SEND body=MAC6+binary; ALL requires zero MAC6.
 * STOP has no body. Reply16=XNA1,token:u32LE,result:i32LE,op:u32LE.
 * No mutation occurs unless a full reply buffer is available. Negative dispatch
 * return means malformed input/no reply. Endpoint results are reply fields.
 * send acceptance is queued, not RF or application delivery. Caller retains
 * request correlation until poll returns AGAIN. No chat framing is imposed. */
int xnow_owner_commands_dispatch(struct xnow_owner_commands *,const void *,size_t,uint8_t reply[16],size_t);
int xnow_owner_commands_poll(struct xnow_owner_commands *,struct xnow_owner_completion *);
/* Native receive output: arbitrary binary and wire metadata, no IPC LMK export. */
int xnow_owner_commands_receive(struct xnow_owner_commands *,void *,size_t,struct xnow_full_received *);
#ifdef __cplusplus
}
#endif
#endif
