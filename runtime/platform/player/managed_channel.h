#ifndef XW_MANAGED_CHANNEL_H
#define XW_MANAGED_CHANNEL_H
#include "managed_rpc.h"
struct xw_managed_channel {struct xw_managed_player *player;int fd;unsigned bound,closing,hello;uint64_t last,deadline;size_t received,expected,sent,total;unsigned char input[XW_RPC_REQUEST_MAX],output[XW_RPC_PACKET_MAX];struct xw_rpc_response response;};
/* Fresh zeroed storage. A trusted manager transfers an already-authorized,
 * connected AF_UNIX stream FD on success. No listener or client authority. */
int xw_managed_channel_open(struct xw_managed_channel *,struct xw_managed_player *,int fd,uint64_t now);
/* Owner-thread only. At most two reads, one dispatch and one <=2048-byte send.
 * Return1 after session release; negative means transport/release failure.
 * Never use return0 as evidence of closed resources. */
int xw_managed_channel_tick(struct xw_managed_channel *,uint64_t now);
int xw_managed_channel_close(struct xw_managed_channel *);
#endif
