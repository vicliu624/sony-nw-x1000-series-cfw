/* Private local player-service framing. This is not an ESP-NOW protocol. */
#ifndef XW_PLAYER_RPC_WIRE_H
#define XW_PLAYER_RPC_WIRE_H
#include "player.h"
#include <stddef.h>
#define XW_RPC_HEADER_BYTES 20u
#define XW_RPC_REQUEST_MAX 166u
#define XW_RPC_PACKET_MAX 13504u
/* Frozen default for pre-extension clients, independent of today's OP_COUNT. */
#define XW_RPC_LEGACY_COMMANDS 0x7fu
enum xw_rpc_kind { XW_RPC_COMMAND = 1, XW_RPC_SNAPSHOT = 2, XW_RPC_BROWSE = 3, XW_RPC_HELLO = 4 };
struct xw_rpc_request {
    uint32_t kind, serial;
    union {
        struct xw_player_command command;
        struct xw_media_query query;
        struct {
            uint32_t known_commands;
            unsigned present;
        } hello;
    } body;
};
struct xw_rpc_response {
    uint32_t kind, serial;
    int result;
    union {
        uint32_t commands;
        struct xw_player_snapshot snapshot;
        struct {
            struct xw_media_page page;
            struct xw_media_item items[XW_MEDIA_PAGE_MAX];
        } browse;
    } body;
};
/* Frames explicitly encode fields; C padding, pointers and native enum layout
 * never enter the channel. Bytes after each string's NUL are zeroed on send. */
#ifdef __cplusplus
extern "C" {
#endif
int xw_rpc_header(const unsigned char *, unsigned *reply, uint32_t *kind, uint32_t *serial,
                  uint32_t *body_bytes);
int xw_rpc_request_body_valid(uint32_t kind, uint32_t body_bytes);
static inline uint32_t xw_rpc_hello_commands(const struct xw_rpc_request *r) {
    return r->body.hello.present ? r->body.hello.known_commands : XW_RPC_LEGACY_COMMANDS;
}
int xw_rpc_encode_request(const struct xw_rpc_request *, unsigned char *, size_t, size_t *);
int xw_rpc_decode_request(const unsigned char *, size_t, struct xw_rpc_request *);
int xw_rpc_encode_response(const struct xw_rpc_response *, unsigned char *, size_t, size_t *);
int xw_rpc_decode_response(const unsigned char *, size_t, struct xw_rpc_response *);
#ifdef __cplusplus
}
#endif
#endif
