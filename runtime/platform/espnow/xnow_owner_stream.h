#ifndef XNOW_OWNER_STREAM_H
#define XNOW_OWNER_STREAM_H
#include "xnow_owner_commands.h"
/* Experimental SDK pipe transport. Caller must ignore SIGPIPE before stepping,
 * serialize all access, and keep controller/lease/handoff alive until restoration.
 * No file persistence, system writes, image loading or process exits here. */
struct xnow_owner_stream {
 struct xnow_owner_commands *commands;
 int input,output,pid,fault;uint64_t device[2],inode[2];
 size_t used,needed,output_bytes,written;
 uint8_t request[XNOW_OWNER_COMMAND_MAX],response[32+XNOW_ESPNOW_V2_MAX];
};
#ifdef __cplusplus
extern "C" {
#endif
/* Fresh object. Requires distinct, already nonblocking readonly/writeonly FIFO
 * descriptions. Duplicates as CLOEXEC without changing caller file flags. */
int xnow_owner_stream_open(struct xnow_owner_stream *,struct xnow_owner_commands *,int input,int output);
/* At most one bounded read or write per step. Checks pipe HUP before dispatch,
 * including HUP with unread data. Bad framing, EOF, reused FDs or I/O failure
 * wipe staged keys/data and request controller STOP, never claim restoration. */
int xnow_owner_stream_step(struct xnow_owner_stream *);
/* Output slot must be empty before consuming an endpoint event. PENDING means
 * no bytes copied; caller retains event. Frames have magic+total:u32LE.
 * XNT1:32 bytes, token:u32,result:i32,MAC6,reserved2,status:u32,raw:u32.
 * XNR1:32+data bytes, token0:u32,MAC6,version:u8,elements:u8,random4,
 * RX flags:u32LE (offset24),reserved4,data. Flags: broadcast1, authenticated2.
 * Command ACK is the existing fixed16-byte XNA1 response. */
int xnow_owner_stream_writable(const struct xnow_owner_stream *);
int xnow_owner_stream_completion(struct xnow_owner_stream *,const struct xnow_owner_completion *);
int xnow_owner_stream_receive(struct xnow_owner_stream *,const void *,size_t,const struct xnow_full_received *);
/* Close only these duplicate pipe descriptions; does not release radio lease or
 * managed foreground. Reports FD replacement without closing its replacement. */
int xnow_owner_stream_close(struct xnow_owner_stream *);
#ifdef __cplusplus
}
#endif
#endif
