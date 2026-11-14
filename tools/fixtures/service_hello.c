/* Actual codec and managed request/grant paths. No sockets or native player. */
#include "../../runtime/platform/player/managed_rpc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned writes;
static int snapshot(void *context, struct xw_player_snapshot *out) {
    (void)context;
    memset(out, 0, sizeof *out);
    return 0;
}
static int command(void *context, const struct xw_player_command *request) {
    (void)context;
    assert(request->operation == XW_OP_SET_PLAY_MODE);
    assert(request->value >= XW_MODE_NORMAL && request->value < XW_MODE_COUNT);
    writes++;
    return XW_PLAYER_ACCEPTED;
}
static int close_backend(void *context) {
    (void)context;
    return 0;
}
static void hello(struct xw_managed_player *player, unsigned present, uint32_t mask,
                  uint32_t expected) {
    struct xw_rpc_request request = {0}, decoded;
    request.kind = XW_RPC_HELLO;
    request.serial = 9;
    request.body.hello.present = present;
    request.body.hello.known_commands = mask;
    unsigned char frame[32], response[32];
    size_t bytes, returned;
    assert(!xw_rpc_encode_request(&request, frame, sizeof frame, &bytes));
    assert(bytes == (present ? 24 : 20));
    assert(!xw_rpc_decode_request(frame, bytes, &decoded));
    assert(decoded.body.hello.present == present);
    if (present)
        assert(decoded.body.hello.known_commands == mask);
    struct xw_rpc_response reply = {0}, parsed;
    assert(!xw_managed_rpc_execute(player, frame, bytes, &reply));
    assert(!reply.result && reply.body.commands == expected);
    assert(!xw_rpc_encode_response(&reply, response, sizeof response, &returned));
    assert(returned == 28 && !xw_rpc_decode_response(response, returned, &parsed));
    assert(parsed.body.commands == expected);
    for (unsigned invalid = 1; invalid <= 5; ++invalid) {
        if (invalid == 4)
            continue;
        frame[16] = (unsigned char)invalid;
        assert(xw_rpc_decode_request(frame, 20 + invalid, &decoded) == XW_PLAYER_PROTOCOL);
    }
}
int main(void) {
    assert(XW_OP_PLAY == 0 && XW_OP_PAUSE == 1 && XW_OP_NEXT == 2 && XW_OP_PREVIOUS == 3 &&
           XW_OP_SET_VOLUME == 4 && XW_OP_STEP_VOLUME == 5 && XW_OP_PLAY_ITEM == 6 &&
           XW_OP_SET_PLAY_MODE == 7);
    static struct xw_session_manager manager;
    static struct xw_player backend;
    static struct xw_managed_player reader, controller;
    struct xw_session_handle read_handle, control_handle;
    struct xw_player_provider provider = {XW_PLAYER_API, 255, 0, snapshot, command, 0,
                                          close_backend};
    assert(!xw_sessions_init(&manager, 19, 7));
    assert(!xw_player_bind(&backend, &provider));
    assert(!xw_session_open(&manager, XW_PLAYER_GRANT_READ, XW_PLAYER_GRANT_READ, &read_handle));
    assert(!xw_managed_player_bind(&reader, &manager, read_handle, &backend));
    assert(!xw_session_open(&manager, 7, 7, &control_handle));
    assert(!xw_managed_player_bind(&controller, &manager, control_handle, &backend));
    hello(&reader, 0, 0, 0);
    hello(&reader, 1, UINT32_MAX, 0);
    hello(&controller, 0, 0, 127);
    hello(&controller, 1, 0, 0);
    hello(&controller, 1, 127, 127);
    hello(&controller, 1, 128, 128);
    hello(&controller, 1, 255, 255);
    hello(&controller, 1, UINT32_MAX, 255);
    hello(&controller, 1, 0x80000000u, 0);
    struct xw_player_command mode = {0};
    mode.operation = XW_OP_SET_PLAY_MODE;
    assert(xw_managed_player_command(&reader, 1, &mode) == XW_PLAYER_UNAVAILABLE && !writes);
    for (unsigned i = 0; i < XW_MODE_COUNT; ++i) {
        mode.value = (int)i;
        assert(xw_managed_player_command(&controller, i + 1, &mode) == XW_PLAYER_ACCEPTED);
        assert(writes == i + 1);
        assert(xw_managed_player_command(&controller, i + 1, &mode) == XW_PLAYER_ACCEPTED);
        assert(writes == i + 1);
        mode.value = (int)((i + 1) % XW_MODE_COUNT);
        assert(xw_managed_player_command(&controller, i + 1, &mode) != XW_PLAYER_ACCEPTED);
        assert(writes == i + 1);
    }
    mode.value = XW_MODE_COUNT;
    assert(xw_managed_player_command(&controller, 20, &mode) == XW_PLAYER_INVALID && writes == 5);
    mode.value = 0;
    strcpy(mode.item.value, "unexpected-id");
    assert(xw_managed_player_command(&controller, 20, &mode) == XW_PLAYER_INVALID && writes == 5);
    assert(!xw_managed_player_close(&reader));
    assert(!xw_managed_player_close(&controller));
    assert(!xw_player_close(&backend));
    puts("HELLO_COMPAT_PASS: legacy seven-bit response, explicit zero/current/future masks, "
         "malformed lengths, CONTROL grant, all modes and no duplicate redispatch");
    return 0;
}
