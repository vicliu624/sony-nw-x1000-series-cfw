#ifndef XW_MANAGED_CONTROL_H
#define XW_MANAGED_CONTROL_H
#include "managed.h"
#include "managed_wire.h"
#include <stddef.h>
/* Private local framing, not radio protocol. Request: XLC1, op:u32,
 * correlation:u64(nonzero), generation:u64, after:u64, limit:u32, reserved:u32.
 * Non-events require after/limit zero. Response: XLR1,op:u32,correlation:u64,
 * result:i32,payload_bytes:u32,payload. Scalars little endian, no native structs.
 * Status payload: state/grants/reason/reserved:u32,epoch:u64,generation:u64.
 * Events payload: next:u64,count/reserved:u32, then sequence/epoch:u64,kind/value:u32.
 * Successful CLOSE returns the retained status receipt. No implicit task stop.
 * PLAY_MODE5 payload: native:u32,menu_index:u32,generation:u64 (16 bytes).
 * Requires an active READ session and a trusted registered reader. Old hosts
 * do not negotiate this extension; callers require a matching qualified host.
 * Outputs unchanged for malformed requests or insufficient output capacity. */
int xw_managed_control_execute(struct xw_managed_player *,const unsigned char *,size_t,unsigned char *,size_t,size_t *);
/* SYNC response payload: sequence:u64 then a complete legacy SNAPSHOT response
 * with nested serial1. Outer correlation is authoritative. Requires1024-byte
 * output capacity and caller-owned large scratch, no large stack response. */
int xw_managed_sync_execute(struct xw_managed_player *,const unsigned char *,size_t,unsigned char *,size_t,size_t *,struct xw_rpc_response *scratch);
#endif
