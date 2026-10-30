/* Private local endpoint. Native AF_UNIX only; no network/radio transport. */
#ifndef XW_PLAYER_RPC_POSIX_H
#define XW_PLAYER_RPC_POSIX_H
#include "provider.h"
#include "rpc_wire.h"
#define XW_PLAYER_RPC_ENDPOINT "sony-x1000.player.v1"
/* Owns packet/response scratch; allocate in static/heap storage. */
struct xw_player_remote {
    char endpoint[96];unsigned bound,timeout_ms;uint32_t serial;
    volatile int *stop;
    unsigned char packet[XW_RPC_PACKET_MAX];
    struct xw_rpc_response response;
};
struct xw_player_rpc_server {
    unsigned bound,busy;unsigned long owner;int listener,peer;
    struct xw_player *player;
    unsigned long long last,deadline;
    size_t received,expected,sent,total;
    unsigned char input[XW_RPC_REQUEST_MAX],output[XW_RPC_PACKET_MAX];
    struct xw_rpc_response response;
};
/* The server never owns/closes player. Its owner calls tick with a monotonic
 * millisecond value. Each tick performs bounded nonblocking IO and at most one
 * provider operation. The provider itself must return promptly. */
#ifdef __cplusplus
extern "C" {
#endif
int xw_player_rpc_server_open(struct xw_player_rpc_server *,struct xw_player *,const char *endpoint);
int xw_player_rpc_server_tick(struct xw_player_rpc_server *,unsigned long long now_ms);
int xw_player_rpc_server_close(struct xw_player_rpc_server *);
/* External-process client only. One deadline covers connect/write/read; no
 * implicit command retry or persistent connection survives an exchange.
 * Caller-owned objects must be zeroed before bind. stop may be NULL. */
int xw_player_remote_bind(struct xw_player *,struct xw_player_remote *,const char *endpoint,unsigned timeout_ms,volatile int *stop);
#ifdef __cplusplus
}
#endif
#endif
