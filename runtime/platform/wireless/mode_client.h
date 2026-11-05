#ifndef XW_WIRELESS_MODE_CLIENT_H
#define XW_WIRELESS_MODE_CLIENT_H
#include "mode_channel.h"
/* One serialized client owner, no authority object, threads, waits or timers.
 * Trusted launcher supplies a connected capability and expected generation. */
struct xw_mode_client {
 uint64_t generation,serial,device,inode;unsigned long thread;
 int pid,fd,bound,fault,pending,sent,owned;uint32_t operation;
 unsigned char request[32],received[80];
};
#ifdef __cplusplus
extern "C" {
#endif
int xw_mode_client_open(struct xw_mode_client *,int fd,uint64_t generation);
int xw_mode_client_begin(struct xw_mode_client *,uint32_t operation,int mode);
/* One nonblocking send or receive. PENDING preserves output. A successful
 * delivery returns0; the operation result is separately in reply.result. */
int xw_mode_client_step(struct xw_mode_client *,struct xw_mode_reply *);
/* Closing a client is not a release/off proof. PENDING means unresolved usage
 * or an in-flight request; the authority still requires qualified retirement. */
int xw_mode_client_close(struct xw_mode_client *);
#ifdef __cplusplus
}
#endif
#endif
