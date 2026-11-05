#ifndef XW_SERVICE_DESCRIPTOR_H
#define XW_SERVICE_DESCRIPTOR_H
#include <stdint.h>
/* Internal transfer over an already-trusted connected AF_UNIX datagram socket.
 * The sender's authority is external; metadata is not authentication. */
struct xw_descriptor_offer {uint64_t generation,session;uint32_t grants;};
int xw_service_descriptor_send(int channel,int connection,const struct xw_descriptor_offer *);
/* Nonblocking; received connection is CLOEXEC before outputs are committed.
 * Serialize fork/exec with adoption on old kernels lacking atomic CLOEXEC. */
int xw_service_descriptor_receive(int channel,int *connection,struct xw_descriptor_offer *);
#endif
