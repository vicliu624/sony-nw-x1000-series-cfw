#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_owner_runtime.h"
#include "xnow_handoff.h"
#include "xnow_security.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int runtime_fcntl(int, int, ...) __asm__("fcntl");
static void erase(void *p, size_t n) {
    volatile uint8_t *v = p;
    while (n--)
        *v++ = 0;
}
static void clear_received(struct xnow_owner_runtime *r) {
    erase(r->receive, sizeof r->receive);
    erase(&r->received, sizeof r->received);
    r->receive_pending = 0;
}
static int writer_valid(struct xnow_owner_runtime *r) {
    struct stat st;
    int flags = runtime_fcntl(r->writer, F_GETFL);
    return flags >= 0 && (flags & O_ACCMODE) == O_WRONLY && !fstat(r->writer, &st) &&
           S_ISFIFO(st.st_mode) && (uint64_t)st.st_dev == r->writer_device &&
           (uint64_t)st.st_ino == r->writer_inode;
}
static void transport_stop(struct xnow_owner_runtime *r) {
    if (r->receive_pending)
        clear_received(r);
    if (r->transport_bound && !r->transport_stopped) {
        r->transport_stopped = 1;
        r->transport.stopping(r->transport.context);
    }
}
static void stop(struct xnow_owner_runtime *r, int failure, unsigned origin) {
    if (failure && !r->application_failure) {
        r->application_failure = failure;
        r->application_origin = origin;
    }
    r->commands->stopped = 1;
    xnow_full_control_stop(r->control);
    transport_stop(r);
}
/* The normal callback-boundary check only reads existing flags. On stop, use
 * the controller's existing drain/restore path without granting/releasing
 * ownership. An admitted call may finish; the next producer is not started. */
static int stop_data_if_requested(struct xnow_owner_runtime *r) {
    struct xnow_owner_gate *g = r->gate;
    if (r->control->stop_requested || r->commands->stopped || g->stopping || g->data_revoked ||
        (g->stop_token && *g->stop_token)) {
        r->commands->stopped = 1;
        if (!r->control->stop_requested)
            xnow_full_control_stop(r->control);
        transport_stop(r);
        return 1;
    }
    return 0;
}
int xnow_owner_runtime_init(struct xnow_owner_runtime *r, struct xnow_full_control *c,
                            struct xnow_owner_gate *g, struct xnow_owner_stream *s,
                            struct xnow_owner_commands *commands, int writer,
                            const uint8_t cookie[16], void *context,
                            int (*prepare)(void *, struct xnow_endpoint *, const uint8_t[6]),
                            int (*close_data)(void *)) {
    if (!r || !c || !g || !s || !commands || !cookie || !close_data || writer < 3 ||
        writer == s->input || writer == s->output || writer == g->command_fd ||
        writer == g->socket_fd || c->session.phase != XNOW_SESSION_STARTING || !c->initialized ||
        c->manager.held || c->job.pid || c->endpoint_ready || c->stop_requested ||
        s->commands != commands || s->fault || s->used || s->output_bytes ||
        s->pid != (int)getpid() || g->pid != (int)getpid() || s->device[0] != g->command_device ||
        s->inode[0] != g->command_inode || c->options.context != g ||
        c->options.lease_valid != xnow_owner_gate_radio_valid ||
        (c->options.encrypted_limit && !prepare) || !xnow_owner_gate_radio_valid(g))
        return XNOW_ARGUMENT;
    unsigned any = 0;
    for (unsigned i = 0; i < 16; i++)
        any |= cookie[i];
    if (!any)
        return XNOW_ARGUMENT;
    memset(r, 0, sizeof *r);
    r->control = c;
    r->gate = g;
    r->stream = s;
    r->commands = commands;
    r->writer = writer;
    r->pid = (int)getpid();
    r->context = context;
    r->prepare = prepare;
    r->close_data = close_data;
    memcpy(r->cookie, cookie, 16);
    struct stat st;
    int flags = runtime_fcntl(writer, F_GETFL);
    if (flags < 0 || (flags & O_ACCMODE) != O_WRONLY || fstat(writer, &st) ||
        !S_ISFIFO(st.st_mode) ||
        ((uint64_t)st.st_dev == s->device[0] && (uint64_t)st.st_ino == s->inode[0]) ||
        ((uint64_t)st.st_dev == s->device[1] && (uint64_t)st.st_ino == s->inode[1]) ||
        runtime_fcntl(writer, F_SETFD, FD_CLOEXEC) < 0) {
        r->fault = 1;
        return XNOW_IDENTITY;
    }
    r->writer_device = (uint64_t)st.st_dev;
    r->writer_inode = (uint64_t)st.st_ino;
    return xnow_owner_commands_control(commands, c);
}
int xnow_owner_runtime_transport(struct xnow_owner_runtime *r,
                                 const struct xnow_owner_transport *transport) {
    if (!r || r->pid != (int)getpid() || !r->control || r->started || r->prepared || r->fault ||
        r->done || r->transport_bound || r->control->stop_requested || !transport ||
        !transport->ready || !transport->idle_step || !transport->receive || !transport->stopping)
        return XNOW_ARGUMENT;
    r->transport = *transport;
    r->transport_bound = 1;
    return 0;
}
static int finish(struct xnow_owner_runtime *r) {
    transport_stop(r);
    if (!r->cleaned) {
        if (r->close_data(r->context)) {
            r->fault = 1;
            return XNOW_UNCERTAIN;
        }
        r->cleaned = 1;
    }
    if (!r->released) {
        if (xnow_owner_stream_close(r->stream) || xnow_owner_gate_release(r->gate, r->control)) {
            r->fault = 1;
            return XNOW_UNCERTAIN;
        }
        r->released = 1;
    }
    if (!writer_valid(r)) {
        r->fault = 1;
        return XNOW_UNCERTAIN;
    }
    int result = xnow_handoff_notify(r->writer, r->cookie, r->control);
    if (result == XNOW_PENDING)
        return result;
    if (result || close(r->writer)) {
        r->fault = 1;
        return XNOW_UNCERTAIN;
    }
    r->writer = -1;
    erase(r->cookie, sizeof r->cookie);
    erase(r->receive, sizeof r->receive);
    r->done = 1;
    return 0;
}
static int data_ready(struct xnow_owner_runtime *r, int *ready) {
    if (!r->transport_bound) {
        *ready = 1;
        return 0;
    }
    int value = r->transport.ready(r->transport.context);
    if (value < 0 || value > 1) {
        stop(r, value < 0 ? value : XNOW_ARGUMENT, 6);
        return XNOW_PENDING;
    }
    if (stop_data_if_requested(r))
        return XNOW_PENDING;
    *ready = value;
    return 0;
}
static int poll_completion(struct xnow_owner_runtime *r) {
    struct xnow_owner_completion complete;
    int result = xnow_owner_commands_poll(r->commands, &complete);
    if (result < 0) {
        stop(r, result, 4);
        return XNOW_PENDING;
    }
    if (stop_data_if_requested(r))
        return XNOW_PENDING;
    if (!result) {
        if (xnow_owner_stream_completion(r->stream, &complete))
            stop(r, XNOW_UNCERTAIN, 3);
        return XNOW_PENDING;
    }
    return XNOW_AGAIN;
}
static void receive_one(struct xnow_owner_runtime *r) {
    if (r->receive_pending)
        return;
    struct xnow_full_received received;
    int result = xnow_owner_commands_receive(r->commands, r->receive, sizeof r->receive, &received);
    if (!result) {
        r->receive_stats.decoded++;
        if (stop_data_if_requested(r))
            goto done;
        int consumed = 0;
        if (r->transport_bound) {
            consumed = r->transport.receive(r->transport.context, &received, r->receive,
                                            received.info.payload_bytes);
            if (consumed < 0 || consumed > 1) {
                stop(r, consumed < 0 ? consumed : XNOW_ARGUMENT, 6);
                goto done;
            }
            if (stop_data_if_requested(r))
                goto done;
        }
        if (consumed) {
            r->receive_stats.sideband++;
            goto done;
        }
        int ready = 0;
        if (data_ready(r, &ready))
            goto done;
        if (!ready) {
            r->receive_stats.gated++;
            r->dropped++;
            goto done;
        }
        if (r->transport_bound) {
            r->received = received;
            r->receive_pending = 1;
        } else if (xnow_owner_stream_receive(r->stream, r->receive, received.info.payload_bytes,
                                             &received))
            stop(r, XNOW_UNCERTAIN, 3);
        else
            r->receive_stats.forwarded++;
    } else if (result == XNOW_SECURITY_AUTH || result == XNOW_SECURITY_REPLAY ||
               result == XNOW_SECURITY_FORMAT || result == XNOW_RADIO_REJECTED ||
               result == XNOW_ENDPOINT_CRYPTO_UNAVAILABLE) {
        r->dropped++;
        if (result == XNOW_SECURITY_AUTH)
            r->receive_stats.auth++;
        else if (result == XNOW_SECURITY_REPLAY)
            r->receive_stats.replay++;
        else if (result == XNOW_SECURITY_FORMAT)
            r->receive_stats.format++;
        else
            r->receive_stats.refused++;
    } else if (result < 0) {
        r->receive_stats.other_error++;
        stop(r, result, 5);
    }
done:
    (void)stop_data_if_requested(r);
    if (!r->receive_pending)
        erase(r->receive, sizeof r->receive);
}
static int publish_received(struct xnow_owner_runtime *r) {
    if (!r->receive_pending)
        return 0;
    if (stop_data_if_requested(r) || !xnow_owner_stream_writable(r->stream))
        return XNOW_PENDING;
    if (xnow_owner_stream_receive(r->stream, r->receive, r->received.info.payload_bytes,
                                  &r->received)) {
        stop(r, XNOW_UNCERTAIN, 3);
        return XNOW_PENDING;
    }
    r->receive_stats.forwarded++;
    clear_received(r);
    return XNOW_PENDING;
}
/* A transport may own control TX only after app TX and queued replies drain.
 * It never consumes an application request while admission is held. */
static int transport_progress(struct xnow_owner_runtime *r, struct xnow_endpoint *endpoint) {
    if (xnow_owner_stream_flush(r->stream) < 0) {
        stop(r, XNOW_IO, 3);
        return XNOW_PENDING;
    }
    if (stop_data_if_requested(r) || !xnow_owner_stream_writable(r->stream))
        return XNOW_PENDING;
    if (r->commands->sending && poll_completion(r) == XNOW_PENDING)
        return XNOW_PENDING;
    if (stop_data_if_requested(r))
        return XNOW_PENDING;
    if (r->receive_pending)
        return publish_received(r);
    /* A queued peer restart can revoke the key that was ready at turn entry.
     * Inspect one transport event before admitting any new application request. */
    receive_one(r);
    if (stop_data_if_requested(r) || !xnow_owner_stream_writable(r->stream))
        return XNOW_PENDING;
    int busy = r->commands->sending;
    if (!busy) {
        int result = r->transport.idle_step(r->transport.context, endpoint);
        if (result < 0 || result > XNOW_PENDING) {
            stop(r, result < 0 ? result : XNOW_ARGUMENT, 6);
            return XNOW_PENDING;
        }
        if (stop_data_if_requested(r))
            return XNOW_PENDING;
        busy = result == XNOW_PENDING;
    }
    int ready = 0;
    if (data_ready(r, &ready))
        return XNOW_PENDING;
    if (busy || !ready)
        return XNOW_PENDING;
    return 0;
}
static int advance_runtime(struct xnow_owner_runtime *r, void *context,
                           int (*advance)(void *, struct xnow_full_control *)) {
    if (!r || !r->control || r->pid != (int)getpid())
        return XNOW_ARGUMENT;
    if (r->done)
        return 0;
    if (r->fault)
        return XNOW_UNCERTAIN;
    int phase = advance
                    ? xnow_owner_gate_step_with_controller(r->gate, r->control, context, advance)
                    : xnow_owner_gate_step(r->gate, r->control);
    if (phase < 0)
        return phase;
    if (r->control->stop_requested)
        transport_stop(r);
    if (xnow_full_control_finished(r->control))
        return finish(r);
    if (phase != XNOW_SESSION_READY)
        return XNOW_PENDING;
    if (r->control->stop_requested)
        return XNOW_PENDING;
    if (xnow_owner_gate_storage_guard(r->gate)) {
        stop(r, XNOW_IDENTITY, 1);
        return XNOW_PENDING;
    }
    if (stop_data_if_requested(r))
        return XNOW_PENDING;
    struct xnow_endpoint *endpoint = xnow_full_control_endpoint(r->control);
    if (!endpoint) {
        stop(r, XNOW_IDENTITY, 1);
        return XNOW_PENDING;
    }
    if (!r->prepared) {
        if (r->prepare) {
            int result = r->prepare(r->context, endpoint, r->control->local_mac);
            if (result) {
                stop(r, result, 2);
                return XNOW_PENDING;
            }
        }
        if (stop_data_if_requested(r))
            return XNOW_PENDING;
        if (r->control->options.encrypted_limit &&
            (!endpoint->crypto.context || !endpoint->crypto.prepare || !endpoint->crypto.send ||
             !endpoint->crypto.receive || !endpoint->crypto.forget || !endpoint->crypto.clear)) {
            stop(r, XNOW_ENDPOINT_CRYPTO_UNAVAILABLE, 2);
            return XNOW_PENDING;
        }
        r->prepared = 1;
    }
    if (r->transport_bound && transport_progress(r, endpoint))
        return XNOW_PENDING;
    if (xnow_owner_stream_step(r->stream) < 0) {
        stop(r, XNOW_IO, 3);
        return XNOW_PENDING;
    }
    if (stop_data_if_requested(r))
        return XNOW_PENDING;
    if (!xnow_owner_stream_writable(r->stream))
        return XNOW_PENDING;
    if (poll_completion(r) == XNOW_PENDING)
        return XNOW_PENDING;
    if (r->transport_bound)
        (void)publish_received(r);
    else
        receive_one(r);
    return XNOW_PENDING;
}
static int runtime_step(struct xnow_owner_runtime *r, void *context,
                        int (*advance)(void *, struct xnow_full_control *)) {
    if (!r || !r->control || r->pid != (int)getpid())
        return XNOW_ARGUMENT;
    if (r->stepping)
        return XNOW_PENDING;
    r->started = 1;
    r->stepping = 1;
    int result = advance_runtime(r, context, advance);
    r->stepping = 0;
    return result;
}
int xnow_owner_runtime_step(struct xnow_owner_runtime *r) { return runtime_step(r, 0, 0); }
int xnow_owner_runtime_step_with_controller(struct xnow_owner_runtime *r, void *context,
                                            int (*advance)(void *, struct xnow_full_control *)) {
    if (!advance)
        return XNOW_ARGUMENT;
    return runtime_step(r, context, advance);
}
