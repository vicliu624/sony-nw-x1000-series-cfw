#ifndef XW_MANAGED_REMOTE_H
#define XW_MANAGED_REMOTE_H
#include "managed_codec.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Private synchronous client transport, worker-thread only. Fresh zeroed
 * context, already-authorized connected AF_UNIX stream, explicit clock adapter.
 * Adoption owns the descriptor; detach never asserts server cleanup completed. */
struct xw_managed_remote {int fd;unsigned bound,busy,timeout;volatile int *stop;void *clock_context;int (*clock)(void *,uint64_t *);unsigned char reply[XW_RPC_PACKET_MAX];size_t reply_bytes;};
int xw_managed_remote_adopt(struct xw_managed_remote *,int fd,unsigned timeout_ms,volatile int *stop,void *,int (*monotonic_ms)(void *,uint64_t *));
/* Request validated before sending; no automatic retry/reconnect. Response
 * scratch belongs to context and is valid only on success. App outputs must
 * be committed by the matching codec after this returns0. */
int xw_managed_remote_exchange(struct xw_managed_remote *,const unsigned char *,size_t);
int xw_managed_remote_detach(struct xw_managed_remote *);
#ifdef __cplusplus
}
#endif
#endif
