/* Actual local RPC server/client; synthetic player and no device operations. */
#define _POSIX_C_SOURCE 200809L
#include "../../runtime/platform/player/rpc_posix.h"
#ifdef XW_HELLO_MANAGED_CLIENT
#include "../../runtime/platform/player/managed_client.h"
#endif
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#ifdef XW_HELLO_LEGACY_CLIENT
typedef char really_old_client[(XW_OP_COUNT == 7) ? 1 : -1];
#endif
int hb_monotonic_millis(unsigned long long *out) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now))
        return -1;
    *out = (unsigned long long)now.tv_sec * 1000 + (unsigned)now.tv_nsec / 1000000;
    return 0;
}
static struct xw_player player;
static struct xw_player_remote remote;
#ifndef XW_HELLO_LEGACY_CLIENT
static int snapshot(void *unused, struct xw_player_snapshot *out) {
    (void)unused;
    memset(out, 0, sizeof *out);
    out->valid = XW_PF_STATE;
    out->state = XW_PLAY_PAUSED;
    return 0;
}
static int command(void *unused, const struct xw_player_command *request) {
    (void)unused;
    printf("COMMAND %u %d\n", (unsigned)request->operation, request->value);
    fflush(stdout);
    return XW_PLAYER_ACCEPTED;
}
static int close_player(void *unused) {
    (void)unused;
    return 0;
}
#endif
static int legacy_client(const char *endpoint) {
    assert(!xw_player_remote_bind(&player, &remote, endpoint, 1500, 0));
    assert(player.provider.commands == 127);
    struct xw_player_snapshot value;
    assert(!xw_player_snapshot(&player, &value) && value.state == XW_PLAY_PAUSED);
    for (unsigned operation = 0; operation < 7; ++operation) {
        struct xw_player_command request = {0};
        request.operation = (enum xw_player_operation)operation;
        request.value = operation == XW_OP_SET_VOLUME    ? 12
                        : operation == XW_OP_STEP_VOLUME ? -1
                                                         : 0;
        if (operation == XW_OP_PLAY_ITEM)
            strcpy(request.item.value, "fixture:one");
        assert(xw_player_command(&player, &request) == XW_PLAYER_ACCEPTED);
    }
    assert(!xw_player_close(&player));
    puts("FROZEN_7BIT_CLIENT_PASS");
    return 0;
}
#ifndef XW_HELLO_LEGACY_CLIENT
static volatile sig_atomic_t stopped;
static void stop(int signal_number) {
    (void)signal_number;
    stopped = 1;
}
static int server(const char *endpoint) {
    static struct xw_player_rpc_server rpc;
    struct xw_player_provider provider = {XW_PLAYER_API, 255, 0,           snapshot,
                                          command,       0,   close_player};
    assert(!xw_player_bind(&player, &provider));
    assert(!xw_player_rpc_server_open(&rpc, &player, endpoint));
    assert(signal(SIGTERM, stop) != SIG_ERR);
    puts("READY");
    fflush(stdout);
    while (!stopped) {
        unsigned long long now;
        assert(!hb_monotonic_millis(&now));
        int result = xw_player_rpc_server_tick(&rpc, now);
        assert(result == 0 || result == 1 || result == XW_PLAYER_IO ||
               result == XW_PLAYER_PROTOCOL);
        poll(0, 0, 1);
    }
    assert(!xw_player_rpc_server_close(&rpc));
    assert(!xw_player_close(&player));
    return 0;
}
static void write_all(int fd, const void *source, size_t bytes) {
    const unsigned char *p = source;
    while (bytes) {
        ssize_t n = write(fd, p, bytes);
        if (n < 0 && errno == EINTR)
            continue;
        assert(n > 0);
        p += n;
        bytes -= (size_t)n;
    }
}
static int probes(const char *endpoint) {
    const uint32_t masks[] = {0, 127, 128, 255, UINT32_MAX, 0x80000000u};
    for (unsigned index = 0; index < sizeof masks / sizeof *masks; ++index) {
        int fd = socket(AF_UNIX, SOCK_STREAM, 0);
        assert(fd >= 0);
        struct sockaddr_un address = {0};
        address.sun_family = AF_UNIX;
        memcpy(address.sun_path + 1, endpoint, strlen(endpoint));
        assert(
            !connect(fd, (struct sockaddr *)&address,
                     (socklen_t)(offsetof(struct sockaddr_un, sun_path) + 1 + strlen(endpoint))));
        struct xw_rpc_request request = {0};
        request.kind = XW_RPC_HELLO;
        request.serial = index + 1;
        request.body.hello.present = 1;
        request.body.hello.known_commands = masks[index];
        unsigned char frame[64];
        size_t bytes;
        assert(!xw_rpc_encode_request(&request, frame, sizeof frame, &bytes) && bytes == 24);
        write_all(fd, frame, 20);
        struct pollfd pending = {fd, POLLIN, 0};
        assert(!poll(&pending, 1, 10));
        write_all(fd, frame + 20, 1);
        assert(!poll(&pending, 1, 10));
        write_all(fd, frame + 21, 3);
        size_t received = 0;
        while (received < 28) {
            assert(poll(&pending, 1, 2000) > 0);
            ssize_t n = read(fd, frame + received, 28 - received);
            assert(n > 0);
            received += (size_t)n;
        }
        struct xw_rpc_response reply;
        assert(!xw_rpc_decode_response(frame, received, &reply));
        assert(!reply.result && reply.serial == request.serial &&
               reply.body.commands == (masks[index] & 255));
        close(fd);
    }
    puts("HELLO_FRAGMENTED_MASKS_PASS");
    return 0;
}
#endif
int main(int argc, char **argv) {
#ifdef XW_HELLO_MANAGED_CLIENT
    if (argc == 2 && !strcmp(argv[1], "--managed")) {
        static struct xw_managed_client client;
        assert(!xw_managed_client_bind_stock(&player, &client, 3, 23, 3000, 0));
        assert(player.provider.commands == (1u << XW_OP_NEXT));
        struct xw_player_command request = {0};
        request.operation = XW_OP_NEXT;
        assert(xw_player_command(&player, &request) == XW_PLAYER_ACCEPTED);
        struct xw_session_snapshot receipt;
        assert(!xw_managed_client_status(&client, &receipt) && receipt.state == XW_SESSION_ACTIVE);
        assert(!xw_managed_client_end(&client, &receipt) && receipt.state == XW_SESSION_CLOSED);
        assert(!xw_player_close(&player));
        puts("FROZEN_7BIT_MANAGED_CLIENT_PASS");
        return 0;
    }
#endif
    if (argc != 3)
        return 64;
    if (!strcmp(argv[1], "--client"))
        return legacy_client(argv[2]);
#ifndef XW_HELLO_LEGACY_CLIENT
    if (!strcmp(argv[1], "--server"))
        return server(argv[2]);
    if (!strcmp(argv[1], "--probes"))
        return probes(argv[2]);
#endif
    return 64;
}
