/* Actual managed host service/broker; original playback and native Moma modeled. */
#define main broker_unit_main
#define xw_stock_media_fetch base_media_fetch
#define xw_stock_media_children base_media_children
#include "player_broker.c"
#undef xw_stock_media_fetch
#undef xw_stock_media_children
#undef main
#include "../../runtime/platform/player/host_hook.h"
#include "../../runtime/platform/player/host_managed_service.h"
#include "../../runtime/platform/player/owner_wait.h"
#include "../../runtime/platform/player/host_inherited.h"
#include "../../runtime/platform/player/managed_host.h"
#include "../../runtime/platform/services/descriptor.h"
#include <sys/socket.h>
#include <fcntl.h>
#include <errno.h>
extern int wait_fixture_fcntl(int, int, ...) __asm__("fcntl");
#include <unistd.h>
static unsigned context_ok = 1;
#if defined(XW_HOST_BOUND_NATIVE_REPEAT) || defined(XW_HOST_REVOKED_NATIVE_RETRY)
#include "../../runtime/platform/player/host_prepare_bridge.h"
#include "../../runtime/platform/player/stock_prepare_view.h"
static uint64_t bound_exit_epoch;
static unsigned bound_rf_refused;
static unsigned bound_view_calls;
static unsigned bound_code_refused;
#if defined(XW_HOST_REVOKE_RADIO_WAIT) || defined(XW_HOST_REVOKE_RADIO_READY)
static unsigned bound_rf_pending;
#endif
int xw_player_host_wireless_has_authority(void) { return 1; }
int xw_player_host_wireless_prepare_stop(uint64_t epoch) {
    if (!epoch)
        return -1;
    if (bound_rf_refused)
        return -3;
    if (bound_exit_epoch && bound_exit_epoch != epoch)
        return -2;
    bound_exit_epoch = epoch;
#if defined(XW_HOST_REVOKE_RADIO_WAIT) || defined(XW_HOST_REVOKE_RADIO_READY)
    if (bound_rf_pending) {
        bound_rf_pending--;
        return 1;
    }
#ifdef XW_HOST_REVOKE_RADIO_READY
    context_ok = 0; /* Native view changes during the last radio callback. */
#endif
#endif
    return 0; /* Explicit verified-OFF policy fixture. */
}
int xw_stock_prepare_code_check(void) { return bound_code_refused ? XW_PLAYER_UNSUPPORTED : 0; }
int xw_stock_prepare_view_bind(struct xw_stock_prepare_view *v, uint32_t root, uint32_t command,
                               uint64_t epoch, unsigned long owner) {
    bound_view_calls++;
    assert(root == 0x613e60u && command == 3 && epoch && owner == pthread_self());
#ifdef XW_HOST_NATIVE_PENDING_VIEW
    (void)v;
    return XW_PLAYER_BUSY; /* Model Sony-owned outstanding tokens. */
#else
    if (v->bound)
        return XW_PLAYER_BUSY;
    v->bound = 1;
    v->epoch = epoch;
    return 0;
#endif
}
int xw_stock_prepare_view_check(struct xw_stock_prepare_view *v, uint64_t epoch) {
#ifdef XW_HOST_REVOKED_NATIVE_RETRY
    if (!context_ok)
        return XW_PLAYER_STALE;
#endif
    return v->bound && v->epoch == epoch ? 0 : XW_PLAYER_STALE;
}
int xw_stock_prepare_view_unbind(struct xw_stock_prepare_view *v) {
    v->bound = 0;
    return 0;
}
#endif
static unsigned catalog_calls, continued;
int xw_stock_media_fetch(struct xw_stock_media *s, const struct xw_media_id *id,
                         struct xw_media_item *out) {
    return base_media_fetch(s, id, out);
}
int xw_stock_media_children(struct xw_stock_media *s, const struct xw_stock_children_query *q,
                            struct xw_stock_children_page *out) {
    pthread_mutex_lock((void *)&counters);
    catalog_calls++;
    pthread_mutex_unlock((void *)&counters);
    return base_media_children(s, q, out);
}
int xw_player_host_queue_attach(struct xw_player_broker *b) {
    (void)b;
    return XW_PLAYER_UNAVAILABLE;
}
static int valid(void *c, uint64_t epoch) {
    (void)c;
    return epoch == 19 && context_ok;
}
#ifdef XW_HOST_EXIT_DEPENDENCY
static unsigned dependency_polls;
static int retired(void *c, uint64_t epoch) {
#ifdef XW_HOST_REVOKED_NATIVE_RETRY
    assert(!c && epoch == bound_exit_epoch && !continued && original.initialized);
#else
    assert(!c && epoch == 19 && !continued && original.initialized);
#endif
    assert(xw_player_host_exit_dependency(0, retired) == XW_PLAYER_BUSY);
    dependency_polls++;
#ifdef XW_HOST_REVOKE_RETIREMENT
    if (dependency_polls == 2)
        context_ok = 0;
    if (dependency_polls == 4)
        context_ok = 1;
#endif
    return dependency_polls < 4 ? XW_PLAYER_BUSY : 0;
}
#endif
static int resume(void *c, uint64_t epoch) {
    (void)c;
    assert(epoch == 19 && original.initialized && !backend_closed);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    assert(xw_player_host_prepare_exit(19, 0, valid, resume) == XW_PLAYER_BUSY);
    continued++;
    return 0;
}
static void send_request(int fd, unsigned kind, unsigned serial) {
    struct xw_rpc_request r = {0};
    r.kind = kind;
    r.serial = serial;
    if (kind == XW_RPC_COMMAND)
        r.body.command.operation = XW_OP_NEXT;
    if (kind == XW_RPC_BROWSE)
        r.body.query.limit = 1;
    unsigned char frame[XW_RPC_REQUEST_MAX];
    size_t bytes;
    assert(!xw_rpc_encode_request(&r, frame, sizeof frame, &bytes) &&
           write(fd, frame, bytes) == (ssize_t)bytes);
}
#ifdef XW_HOST_WAIT_BACKPRESSURE
static void check_wait_backpressure(int client) {
    struct xw_owner_wait_fd interest;
    assert(xw_player_host_wait_descriptors(&interest, 1) == 1);
    static char data[4096];
    unsigned attempts = 0;
    for (;;) {
        assert(attempts++ < 1024);
        ssize_t sent = send(interest.fd, data, sizeof data, MSG_DONTWAIT | MSG_NOSIGNAL);
        if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
            break;
        assert(sent > 0 || (sent < 0 && errno == EINTR));
    }
    send_request(client, XW_RPC_SNAPSHOT, 4);
    now++;
    xw_player_host_dispatch(&original);
    assert(xw_player_host_wait_descriptors(&interest, 1) == 1 &&
           interest.events == XW_OWNER_WAIT_WRITE);
    /* Pipelined input must not keep waking a blocked reply writer. */
    send_request(client, XW_RPC_SNAPSHOT, 5);
    struct pollfd readiness = {interest.fd, POLLIN | POLLOUT, 0};
    assert(poll(&readiness, 1, 0) == 1 && (readiness.revents & POLLIN) &&
           !(readiness.revents & POLLOUT));
    int flags = wait_fixture_fcntl(client, F_GETFL);
    assert(flags >= 0 && !wait_fixture_fcntl(client, F_SETFL, flags | O_NONBLOCK));
    attempts = 0;
    for (;;) {
        assert(attempts++ < 2048);
        ssize_t received = read(client, data, sizeof data);
        if (received < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
            break;
        assert(received > 0 || (received < 0 && errno == EINTR));
    }
    readiness.revents = 0;
    assert(poll(&readiness, 1, 0) == 1 && (readiness.revents & POLLOUT));
    now++;
    xw_player_host_dispatch(&original);
    assert(xw_player_host_wait_descriptors(&interest, 1) == 1 &&
           interest.events == XW_OWNER_WAIT_READ);
    now++;
    xw_player_host_dispatch(&original);
    assert(!wait_fixture_fcntl(client, F_SETFL, flags));
    puts("OWNER_WAIT_BACKPRESSURE_PASS");
}
#endif
#ifdef XW_HOST_USER_TOGGLE
static unsigned toggle_polls;
static uint64_t toggle_generation;
static int toggle_retired(void *context, uint64_t generation) {
    assert(!context && generation == toggle_generation && original.initialized && !backend_closed);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
#ifdef XW_HOST_USER_STOP_FAULT
    return ++toggle_polls < 4 ? XW_PLAYER_BUSY : XW_PLAYER_UNAVAILABLE;
#else
    return ++toggle_polls < 4 ? XW_PLAYER_BUSY : 0;
#endif
}
#endif
#ifdef XW_HOST_SETTINGS_REQUESTS
static unsigned settings_seen;
static int settings_reply;
static int settings_request(void *context, uint64_t serial) {
    assert(context == &settings_seen && serial == settings_seen + 1);
    settings_seen++;
    int result = 123;
    assert(xw_player_host_settings_result(serial, &result) == XW_PLAYER_BUSY && result == 123);
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_BUSY);
    assert(xw_player_host_settings_unbind() == XW_PLAYER_BUSY);
    return settings_reply;
}
static void *settings_foreign(void *unused) {
    (void)unused;
    int result = 123;
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_BUSY);
    assert(xw_player_host_settings_unbind() == XW_PLAYER_BUSY);
    assert(xw_player_host_settings_result(1, &result) == XW_PLAYER_BUSY && result == 123);
    return 0;
}
#endif
#ifndef XW_HOST_MANAGED_MAIN
#define XW_HOST_MANAGED_MAIN main
#endif
int XW_HOST_MANAGED_MAIN(void) {
    (void)resume;
    assert(!pthread_mutex_init((void *)&counters, 0));
    struct xw_player_provider p = {XW_PLAYER_API, 1u << XW_OP_NEXT, 0, snapshot, command, 0,
                                   close_backend};
    assert(!xw_player_bind(&original, &p));
    assert(xw_player_host_exit_decision(0, 0, 0, 0) == XW_HOST_EXIT_FACTORY);
    assert(xw_player_host_session_offer(-1, 7, 7, 41) == XW_PLAYER_BUSY);
    xw_player_host_dispatch(&original);
    assert(!xw_player_host_service_phase() && !opened);
#ifdef XW_HOST_BOUND_NATIVE_REPEAT
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()) == 0);
    assert(xw_player_host_resources_idle() == XW_PLAYER_CLOSED);
    assert(xw_player_host_native_resources_idle() == 0);
    int repeated = xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self());
    puts(repeated == 0 ? "BOUND_NATIVE_REPEAT_DELEGATED" : "BOUND_NATIVE_REPEAT_HELD");
    fflush(stdout);
    assert(repeated == 0);
    assert(!bound_view_calls); /* Empty SDK must not gate on Sony's token list. */
    assert(xw_player_host_resources_idle() == XW_PLAYER_CLOSED);
    bound_rf_refused = 1;
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()) ==
           XW_PREPARE_BRIDGE_HANDLED);
    assert(!xw_player_close(&original) && !pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#endif
#ifdef XW_HOST_SETTINGS_REQUESTS
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_UNAVAILABLE);
    assert(xw_player_host_settings_bind(0, 0) == XW_PLAYER_INVALID);
    assert(!xw_player_host_settings_bind(&settings_seen, settings_request));
    assert(xw_player_host_settings_bind(&settings_seen, settings_request) == XW_PLAYER_BUSY);
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_ACCEPTED && !settings_seen);
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_BUSY);
    int answer = 123;
    assert(xw_player_host_settings_result(1, &answer) == XW_PLAYER_BUSY && answer == 123);
    assert(xw_player_host_settings_unbind() == XW_PLAYER_BUSY);
    pthread_t foreign;
    assert(!pthread_create(&foreign, 0, settings_foreign, 0) && !pthread_join(foreign, 0));
    xw_player_host_dispatch(&original);
    assert(settings_seen == 1);
    assert(!xw_player_host_settings_result(1, &answer) && answer == 0);
    for (unsigned i = 0; i < 1000; i++)
        xw_player_host_dispatch(&original);
    assert(settings_seen == 1 && !opened && !xw_player_host_service_phase());
    settings_reply = XW_PLAYER_UNAVAILABLE;
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_ACCEPTED);
    xw_player_host_dispatch(&original);
    assert(settings_seen == 2);
    assert(!xw_player_host_settings_result(2, &answer) && answer == XW_PLAYER_UNAVAILABLE);
    answer = 123;
    assert(xw_player_host_settings_result(1, &answer) == XW_PLAYER_STALE && answer == 123);
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_ACCEPTED);
    xw_player_host_note_native_exit();
    xw_player_host_dispatch(&original);
    assert(settings_seen == 2 && !xw_player_host_settings_result(3, &answer) &&
           answer == XW_PLAYER_CLOSED);
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_CLOSED);
    assert(!xw_player_host_settings_unbind());
    assert(xw_player_host_settings_bind(&settings_seen, settings_request) == XW_PLAYER_CLOSED);
    assert(!xw_player_close(&original) && !pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_SETTINGS_REQUESTS_PASS");
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#endif
    assert(xw_player_host_exit_decision(0, 0, 0, 0) == XW_HOST_EXIT_FACTORY);
    int delivery[2], client;
    struct xw_descriptor_offer identity;
#ifdef XW_HOST_NATIVE_EXIT_EMPTY
    xw_player_host_note_native_exit();
    assert(xw_player_host_resources_idle() == XW_PLAYER_CLOSED);
    assert(xw_player_host_native_resources_idle() == 0);
    assert(xw_player_host_session_offer(-1, 7, 7, 41) == XW_PLAYER_CLOSED && !opened);
    assert(xw_player_host_exit_decision(0, 0, 0, 0) == XW_HOST_EXIT_FACTORY);
    assert(!xw_player_close(&original) && !pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#endif
    assert(!socketpair(AF_UNIX, SOCK_DGRAM, 0, delivery));
#ifdef XW_HOST_INHERITED_DELIVERY
    int wrong_type[2];
    assert(!socketpair(AF_UNIX, SOCK_STREAM, 0, wrong_type));
    assert(xw_player_host_inherited_configure(wrong_type[0], 41, 7) == XW_PLAYER_INVALID);
    close(wrong_type[0]);
    close(wrong_type[1]);
    assert(xw_player_host_inherited_configure(delivery[0], 0, 7) == XW_PLAYER_INVALID);
    assert(xw_player_host_inherited_configure(delivery[0], 41, 8) == XW_PLAYER_INVALID);
    assert(!xw_player_host_inherited_configure(delivery[0], 41, 7));
    assert(xw_player_host_inherited_configure(delivery[0], 41, 7) == XW_PLAYER_CLOSED);
    xw_player_host_dispatch(&original);
    delivery[0] = -1; /* One-shot host handoff now owns/closes this endpoint. */
#else
    assert(!xw_player_host_session_offer(delivery[0], 7, 7, 41));
    assert(xw_player_host_native_resources_idle() == XW_PLAYER_BUSY);
#endif
    assert(!xw_service_descriptor_receive(delivery[1], &client, &identity) &&
           identity.generation == 41 && identity.grants == 7);
    struct xw_owner_wait_fd wake_descriptor = {-1, 0};
    assert(xw_player_host_wait_descriptors(&wake_descriptor, 1) == 1 && wake_descriptor.fd >= 0);
    assert(wake_descriptor.events == XW_OWNER_WAIT_READ);
    assert(wait_fixture_fcntl(wake_descriptor.fd, F_GETFD) >= 0);
#ifdef XW_HOST_EXIT_DEPENDENCY
    assert(!xw_player_host_exit_dependency(0, retired));
    assert(xw_player_host_exit_dependency(0, retired) == XW_PLAYER_INVALID);
    assert(xw_player_host_service_stop() == XW_PLAYER_UNSUPPORTED);
#endif
    assert(xw_player_host_session_offer(delivery[1], 1, 1, 42) == XW_PLAYER_STALE);
    send_request(client, XW_RPC_HELLO, 1);
    for (unsigned i = 0; i < 3; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
    }
    send_request(client, XW_RPC_COMMAND, 2);
    for (unsigned i = 0; i < 2000 && track == 1; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
    }
    assert(track == 2);
    send_request(client, XW_RPC_BROWSE, 3);
    for (unsigned i = 0; i < 2000; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
        pthread_mutex_lock((void *)&counters);
        unsigned ready = catalog_calls;
        pthread_mutex_unlock((void *)&counters);
        if (ready)
            break;
    }
#ifdef XW_HOST_WAIT_BACKPRESSURE
    check_wait_backpressure(client);
#endif
#ifdef XW_HOST_USER_TOGGLE
    for (unsigned cycle = 0; cycle < 4; cycle++) {
        uint64_t generation = 41 + cycle;
        toggle_polls = 0;
        toggle_generation = generation;
        assert(!xw_player_host_stop_dependency(0, toggle_retired));
        assert(xw_player_host_stop_dependency(0, toggle_retired) == XW_PLAYER_INVALID);
        assert(xw_player_host_service_stop() == XW_PLAYER_BUSY);
        assert(xw_player_host_session_offer(delivery[0], 1, 1, generation + 1) == XW_PLAYER_CLOSED);
        for (unsigned i = 0; i < 2000 && xw_player_host_service_phase() == XW_HOST_STOPPING; i++) {
            now++;
            xw_player_host_dispatch(&original);
            poll(0, 0, 1);
        }
#ifdef XW_HOST_USER_STOP_FAULT
        assert(xw_player_host_service_phase() == XW_HOST_FAULT && toggle_polls == 4);
        assert(original.initialized && !backend_closed && !continued);
        assert(xw_player_host_session_offer(delivery[0], 1, 1, generation + 1) != 0);
        for (unsigned i = 0; i < 1000; i++) {
            now++;
            xw_player_host_dispatch(&original);
        }
        assert(xw_player_host_service_phase() == XW_HOST_FAULT && toggle_polls == 4);
        close(client);
        close(delivery[0]);
        close(delivery[1]);
        assert(!pthread_mutex_destroy((void *)&counters));
        puts("PLAYER_HOST_USER_STOP_FAULT_PASS");
        puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
        return 0;
#endif
        assert(xw_player_host_service_phase() == XW_HOST_STOPPED && original.initialized &&
               !backend_closed);
        assert(toggle_polls == 4);
        assert(!xw_player_host_service_stop());
        pthread_mutex_lock((void *)&counters);
        assert(opened == closed && !live);
        unsigned retired_opens = opened;
        pthread_mutex_unlock((void *)&counters);
        for (unsigned i = 0; i < 1000; i++) {
            now++;
            xw_player_host_dispatch(&original);
        }
        pthread_mutex_lock((void *)&counters);
        assert(opened == retired_opens && opened == closed && !live);
        pthread_mutex_unlock((void *)&counters);
        assert(xw_player_host_session_offer(delivery[0], 1, 1, generation) == XW_PLAYER_STALE);
        close(client);
        client = -1;
        if (cycle < 3) {
            assert(!xw_player_host_session_offer(delivery[0], 7, 7, generation + 1));
            assert(!xw_service_descriptor_receive(delivery[1], &client, &identity) &&
                   identity.generation == generation + 1);
            send_request(client, XW_RPC_HELLO, 1);
            for (unsigned i = 0; i < 3; i++) {
                now++;
                xw_player_host_dispatch(&original);
                poll(0, 0, 1);
            }
            unsigned before = track;
            send_request(client, XW_RPC_COMMAND, 2);
            for (unsigned i = 0; i < 2000 && track == before; i++) {
                now++;
                xw_player_host_dispatch(&original);
                poll(0, 0, 1);
            }
            assert(track == before + 1);
        }
    }
    assert(!continued);
    close(delivery[0]);
    close(delivery[1]);
    assert(!xw_player_close(&original));
    assert(!pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_HOST_USER_TOGGLE_PASS");
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#endif
#ifdef XW_HOST_EXIT_FAULT
    context_ok = 0;
    assert(xw_player_host_exit_decision(19, 0, valid, resume) == XW_HOST_EXIT_HOLD);
    assert(xw_player_host_service_phase() == XW_HOST_FAULT && !continued);
    assert(xw_player_host_generation_retired(41) == 0);
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 41) == XW_PLAYER_CLOSED);
    context_ok = 1;
    assert(xw_player_host_exit_decision(19, 0, valid, resume) == XW_HOST_EXIT_HOLD && !continued);
    for (unsigned i = 0; i < 2000; i++) {
        pthread_mutex_lock((void *)&counters);
        unsigned balanced = opened == closed && !live;
        pthread_mutex_unlock((void *)&counters);
        if (balanced)
            break;
        poll(0, 0, 1);
    }
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    assert(original.initialized && !backend_closed);
    close(client);
    close(delivery[0]);
    close(delivery[1]);
    /* Fault intentionally retains SDK objects. Process exit is not a drain pass. */
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#elif defined(XW_HOST_CLOCK_FAILURE)
    clock_fail = 1;
    xw_player_host_dispatch(&original);
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 41) == XW_PLAYER_UNAVAILABLE);
#else
#ifdef XW_HOST_REVOKED_NATIVE_RETRY
#if defined(XW_HOST_REVOKE_RADIO_WAIT) || defined(XW_HOST_REVOKE_RADIO_READY)
    assert(xw_player_host_drain_cancelled_exit(0) == XW_PLAYER_INVALID);
    assert(xw_player_host_drain_cancelled_exit(19) == XW_PLAYER_CLOSED);
    bound_rf_pending = 2;
#endif
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
#else
    assert(xw_player_host_exit_decision(19, 0, valid, resume) == XW_HOST_EXIT_HOLD);
    assert(xw_player_host_exit_decision(19, 0, valid, resume) == XW_HOST_EXIT_HOLD);
#endif
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 41) == XW_PLAYER_CLOSED);
#endif
#if defined(XW_HOST_REVOKE_RADIO_WAIT) || defined(XW_HOST_REVOKE_RADIO_READY)
    assert(xw_player_host_service_phase() == XW_HOST_ACTIVE);
    assert(xw_player_prepare_needs_progress());
#ifdef XW_HOST_REVOKE_RADIO_WAIT
    context_ok = 0;
#endif
    xw_player_prepare_tick();
    context_ok = 1; /* A cancelled continuation must not revive after the wait. */
    for (unsigned i = 0; i < 2000; i++) {
        xw_player_prepare_tick();
        now++;
        xw_player_host_dispatch(&original);
        if (xw_player_host_service_phase() == XW_HOST_FAULT)
            break;
        poll(0, 0, 1);
    }
#endif
#ifdef XW_HOST_REVOKE_DRAIN
    context_ok = 0;
    now++;
    xw_player_host_dispatch(&original);
    assert(xw_player_host_service_phase() == XW_HOST_STOPPING && !continued);
    context_ok = 1; /* Observed revocation must remain sticky during cleanup. */
#endif
    for (unsigned i = 0; i < 2000 && xw_player_host_service_phase() == XW_HOST_STOPPING; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
    }
#ifdef XW_HOST_REVOKED_CONTINUATION
    assert(xw_player_host_service_phase() == XW_HOST_FAULT && original.initialized &&
           !backend_closed && !continued);
    assert(dependency_polls == 4);
    assert(xw_player_host_generation_retired(41) == 1);
    assert(wait_fixture_fcntl(wake_descriptor.fd, F_GETFD) < 0 && errno == EBADF);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    context_ok = 1;
    for (unsigned i = 0; i < 10; i++)
        xw_player_host_dispatch(&original);
    assert(!continued && xw_player_host_service_phase() == XW_HOST_FAULT);
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 42) == XW_PLAYER_CLOSED);
#ifdef XW_HOST_REVOKED_NATIVE_RETRY
    context_ok = 1;
    assert(xw_player_prepare_intercept(0x613e60u, 6, 0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
    assert(xw_player_prepare_intercept(0xdead0001u, 3, 0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()+1) == XW_PREPARE_BRIDGE_HANDLED);
    bound_code_refused = 1;
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
    bound_code_refused = 0;
    bound_rf_refused = 1;
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
    bound_rf_refused = 0;
    assert(xw_player_prepare_intercept(0x613e60u, 3, 0, pthread_self()) == 0);
    assert(xw_player_host_original_exiting());
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 42) == XW_PLAYER_CLOSED && !continued);
#endif
    close(client);
    close(delivery[0]);
    close(delivery[1]);
    assert(!xw_player_close(&original));
    assert(!pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_REVOKED_CONTINUATION_DRAIN_PASS");
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#endif
    assert(xw_player_host_service_phase() == XW_HOST_STOPPED && original.initialized &&
           !backend_closed);
    assert(!xw_player_host_wait_descriptors(&wake_descriptor, 1));
#ifdef XW_HOST_CLOCK_FAILURE
    assert(!continued);
    xw_player_host_dispatch(&original);
    assert(!continued);
    assert(xw_player_host_exit_decision(0, 0, 0, 0) == XW_HOST_EXIT_FACTORY);
#else
    assert(continued == 1);
    xw_player_host_dispatch(&original);
    assert(continued == 1);
#ifdef XW_HOST_EXIT_DEPENDENCY
    assert(dependency_polls == 4);
#endif
    assert(xw_player_host_exit_decision(19, 0, valid, resume) == XW_HOST_EXIT_HOLD &&
           continued == 1);
#endif
    pthread_mutex_lock((void *)&counters);
    assert(catalog_calls && opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    close(client);
    close(delivery[0]);
    close(delivery[1]);
    assert(!xw_player_close(&original));
    assert(!pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
}
