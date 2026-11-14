#define FULL_OWNER_IPC_MAIN unused_legacy_ipc_test
#include "full_owner_ipc.c"
#include "../../runtime/platform/espnow/xnow_owner_runtime.h"

struct transport_context {
    struct xnow_owner_runtime *runtime;
    struct xnow_full_control *controller;
    volatile int *stop;
    int ready, control_requested, control_active, stop_in, reenter;
    unsigned idle_calls, receive_calls, stop_calls, closed, control_completions;
    int input, output;
};
static const uint8_t peer[6] = {2, 1, 2, 3, 4, 5};
static const uint8_t broadcast[6] = {255, 255, 255, 255, 255, 255};

static int owned_storage(void *context) { (void)context; return 0; }
static int prepare_transport(void *context, struct xnow_endpoint *endpoint, const uint8_t local[6])
{
    (void)context; (void)local;
    struct xnow_peer item = {0};
    item.channel = 8;
    item.version = 2;
    memcpy(item.address, peer, 6);
    assert(!xnow_endpoint_add(endpoint, &item));
    memcpy(item.address, broadcast, 6);
    return xnow_endpoint_add(endpoint, &item);
}
static int link_ready(void *context)
{
    struct transport_context *link = context;
    if (link->stop_in == 2) *link->stop = 1;
    return link->ready;
}
static int link_step(void *context, struct xnow_endpoint *endpoint)
{
    struct transport_context *link = context;
    link->idle_calls++;
    assert(!link->runtime->commands->sending);
    assert(!link->runtime->stream->output_bytes);
    if (link->stop_in == 1) *link->stop = 1;
    if (link->reenter) {
        unsigned count = link->idle_calls;
        assert(xnow_owner_runtime_step(link->runtime) == XNOW_PENDING);
        assert(link->idle_calls == count);
    }
    if (link->control_active) {
        struct xnow_endpoint_result event;
        int rc = xnow_endpoint_poll(endpoint, &event);
        if (rc == XNOW_PENDING || rc == XNOW_AGAIN) return XNOW_PENDING;
        assert(!rc);
        if (!endpoint->active) {
            link->control_active = 0;
            link->control_completions++;
        }
        return XNOW_PENDING;
    }
    if (link->control_requested) {
        assert(!endpoint->active && !endpoint->transport->inflight);
        link->control_requested = 0;
        assert(!xnow_endpoint_send(endpoint, broadcast, "CTL", 3));
        link->control_active = 1;
        return XNOW_PENDING;
    }
    return 0;
}
static int link_receive(void *context, const struct xnow_full_received *event,
                        const uint8_t *data, size_t bytes)
{
    struct transport_context *link = context;
    (void)event;
    link->receive_calls++;
    if (link->stop_in == 3) *link->stop = 1;
    if (bytes == 3 && !memcmp(data, "KEY", 3)) {
        link->ready = 1;
        return 1;
    }
    return 0;
}
static void link_stop(void *context)
{
    struct transport_context *link = context;
    link->stop_calls++;
    assert(link->stop_calls == 1);
}
static int close_transport(void *context)
{
    struct transport_context *link = context;
    assert(xnow_full_control_finished(link->controller));
#ifndef XNOW_TRANSPORT_BASELINE
    assert(link->stop_calls == 1);
#endif
    assert(!close(link->input) && !close(link->output));
    link->closed++;
    return 0;
}
static void tick_owner(struct xnow_owner_runtime *runtime, unsigned rounds)
{
    for (unsigned i = 0; i < rounds; i++) assert(xnow_owner_runtime_step(runtime) == XNOW_PENDING);
}
static void assert_empty(int fd)
{
    uint8_t buffer[64];
    assert(read(fd, buffer, sizeof buffer) == -1 && errno == EAGAIN);
}
static void scenario(unsigned stop_in)
{
    (void)stop_in;
    reset();
    fixture_platform_reset();
    connection = 4;
    clients = 0;
    closes = 0;
    int input[2], output[2], handoff[2];
    assert(!pipe(input) && !pipe(output) && !pipe(handoff));
    for (unsigned i = 0; i < 2; i++) { nonblock(input[i]); nonblock(output[i]); }
    nonblock(handoff[0]);
    volatile int stopping = 0;
    struct xnow_owner_gate gate;
    assert(!xnow_owner_gate_open(&gate, input[0], &stopping, NULL, owned_storage));
    struct xnow_full_control control;
    struct xnow_full_fingerprint range = {0x8078, 4, {0}};
    struct xnow_full_profile profile = {layout, 1, &range};
    struct xnow_full_control_options options = {&gate, &profile, guard, guard,
        xnow_owner_gate_radio_valid, random4, 8, 1, 0};
    assert(!xnow_full_control_init(&control, &options));
    struct xnow_owner_commands commands;
    struct xnow_owner_stream stream;
    struct xnow_owner_runtime runtime;
    assert(!xnow_owner_commands_control(&commands, &control));
    assert(!xnow_owner_stream_open(&stream, &commands, input[0], output[1]));
    struct transport_context link = {0};
    link.runtime = &runtime;
    link.controller = &control;
    link.stop = &stopping;
    link.input = input[0];
    link.output = output[1];
    uint8_t cookie[16] = {1};
    assert(!xnow_owner_runtime_init(&runtime, &control, &gate, &stream, &commands,
        handoff[1], cookie, &link, prepare_transport, close_transport));
#ifndef XNOW_TRANSPORT_BASELINE
    struct xnow_owner_transport ops = {&link, link_ready, link_step, link_receive, link_stop};
    assert(!xnow_owner_runtime_transport(&runtime, &ops));
#endif
    for (unsigned i = 0; !runtime.prepared; i++) { assert(i < 200); tick_owner(&runtime, 1); }
    uint8_t command_bytes[XNOW_OWNER_COMMAND_MAX], reply[32];
    size_t bytes = request(command_bytes, XNOW_OWNER_SEND, 23, 10);
    memcpy(command_bytes + 16, peer, 6);
    memcpy(command_bytes + 22, "DATA", 4);
    assert(write(input[1], command_bytes, bytes) == (ssize_t)bytes);
    tick_owner(&runtime, 5);
#ifdef XNOW_TRANSPORT_BASELINE
    assert(read(output[0], reply, 16) == 16 && !memcmp(reply, "XNA1", 4));
    puts("BASELINE_PREMATURE_SEND_ACK");
#else
    assert_empty(output[0]);
    assert(!stream.used && !stream.output_bytes && !commands.sending && !submits);
    link.reenter = 1;
    receive((const unsigned char *)"KEY", 3);
    tick_owner(&runtime, 1);
    link.reenter = 0;
    assert(link.ready && runtime.receive_stats.sideband == 1);
    assert_empty(output[0]);
    unsigned have_ack = 0;
    for (unsigned i = 0; i < 20 && !have_ack; i++) {
        tick_owner(&runtime, 1);
        ssize_t count = read(output[0], reply, 16);
        if (count > 0) { assert(count == 16); have_ack = 1; }
        else assert(errno == EAGAIN);
    }
    assert(have_ack && !memcmp(reply, "XNA1", 4) && reply[4] == 23 && !reply[8]);
    while (!control.backend.inflight) tick_owner(&runtime, 1);
    /* A control send must not borrow the app's pending completion token. */
    link.control_requested = 1;
    unsigned before = link.idle_calls;
    tick_owner(&runtime, 2);
    assert(link.idle_calls == before && !link.control_active);
    done(0);
    unsigned have_completion = 0;
    for (unsigned i = 0; i < 30 && !have_completion; i++) {
        tick_owner(&runtime, 1);
        ssize_t count = read(output[0], reply, 32);
        if (count > 0) { assert(count == 32); have_completion = 1; }
        else assert(errno == EAGAIN);
    }
    assert(have_completion && !memcmp(reply, "XNT1", 4) && reply[8] == 23);
    for (unsigned i = 0; !control.backend.inflight; i++) { assert(i < 30); tick_owner(&runtime, 1); }
    assert(link.control_active && !commands.sending);
    assert_empty(output[0]);
    done(0);
    tick_owner(&runtime, 4);
    assert(link.control_completions == 1);
    assert_empty(output[0]);
    link.stop_in = (int)stop_in;
    if (stop_in == 3) receive((const unsigned char *)"DATA", 4);
    if (stop_in) tick_owner(&runtime, 1);
#endif
    stopping = 1;
    for (unsigned i = 0; !runtime.done; i++) {
        assert(i < 300);
        if (control.backend.inflight) done(0);
        int result = xnow_owner_runtime_step(&runtime);
        assert(result == 0 || result == XNOW_PENDING);
    }
    assert(link.closed == 1);
    assert(read(output[0], reply, sizeof reply) == 0);
    uint8_t receipt[32];
    assert(read(handoff[0], receipt, sizeof receipt) == 32 && !memcmp(receipt, "XRFDONE1", 8));
    assert(read(handoff[0], receipt, 1) == 0);
    close(input[1]); close(output[0]); close(handoff[0]);
}

int main(void)
{
    assert(signal(SIGPIPE, SIG_IGN) != SIG_ERR);
    scenario(0);
#ifndef XNOW_TRANSPORT_BASELINE
    scenario(1); scenario(2); scenario(3);
    puts("OWNER_TRANSPORT_RUNTIME_PASS");
#endif
    return 0;
}
