/* Actual RF owner preparation with modeled stock socket/peer operations.
 * This checks caller resource lifetime, not physical receive admission. */
#define _DEFAULT_SOURCE
#define XNOW_REMOTE_MANAGED
#define XNOW_REMOTE_MODE_VIEW
#include "runtime/platform/espnow/xnow_full_control.h"
#include "runtime/platform/espnow/xnow_owner_stream.h"
#include "runtime/platform/espnow/native_environment.h"
#include "runtime/apps/wireless-remote/run_profile.h"
#include "runtime/apps/wireless-remote/startup_result.h"
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

extern int owner_fcntl(int, int, ...) __asm__("fcntl");
static struct xnow_full_control owner_control;
static struct xnow_owner_stream owner_stream;
static struct xnow_native_security native_security;
static struct xnow_native_profile native_environment;
static unsigned pairing_listener;
static volatile int stop_requested;
static const uint8_t pairing_broadcast[6] = {255, 255, 255, 255, 255, 255};
static uint8_t peer_address[6] = {2, 1, 2, 3, 4, 5};
static unsigned membership_count, opens, closes, endpoint_calls, ready_events;
static int socket_failure, security_failure, endpoint_failure;
static int parent_failure, stop_in_security, stop_in_peer;
static unsigned parent_checks;
static uint32_t pairing_queue_head, pairing_queue_drops;
static unsigned long long pairing_queue_sample_at;

/* ACTUAL_RECEIVE_MEMBERSHIP */

int socket(int family, int kind, int protocol)
{
    assert(family == AF_PACKET && kind == SOCK_DGRAM && protocol == 0);
    opens++;
    return socket_failure == 1 ? -1 : 19;
}

int owner_fcntl(int fd, int command, ...)
{
    va_list args;
    va_start(args, command);
    int flags = va_arg(args, int);
    va_end(args);
    assert(fd == 19 && command == F_SETFD && flags == FD_CLOEXEC);
    return 0;
}

int shared_stock_ioctl(int fd, unsigned long command, ...)
{
    va_list args;
    va_start(args, command);
    struct ifreq *request = va_arg(args, struct ifreq *);
    va_end(args);
    assert(fd == 19 && !strcmp(request->ifr_name, "eth0"));
    if (command == SIOCGIFINDEX) request->ifr_ifindex = 7;
    else {
        assert(command == SIOCGIFFLAGS);
        request->ifr_flags = IFF_UP | IFF_PROMISC;
    }
    return 0;
}

int shared_stock_setsockopt(int fd, int level, int option,
                            const void *payload, socklen_t bytes)
{
    const struct packet_mreq *request = payload;
    assert(fd == 19 && level == SOL_PACKET && option == PACKET_ADD_MEMBERSHIP);
    assert(bytes == sizeof(*request) && request->mr_ifindex == 7);
    assert(request->mr_type == PACKET_MR_PROMISC && !membership_count);
    if (socket_failure == 2) return -1;
    membership_count++;
    return 0;
}

int close(int fd)
{
    assert(fd == 19);
    closes++;
    membership_count = 0;
    return 0;
}

static int prepare_security(void *context, struct xnow_full_control *control)
{
    (void)context;
    assert(control == &owner_control);
    if (stop_in_security) stop_requested = 1;
    return security_failure;
}

int xnow_endpoint_add(struct xnow_endpoint *endpoint, const struct xnow_peer *peer)
{
    assert(endpoint == &owner_control.endpoint && peer->channel == 1);
    assert(peer->encrypt == !pairing_listener);
    endpoint_calls++;
    if (stop_in_peer) stop_requested = 1;
    return endpoint_failure;
}

int xnow_owner_stream_receive(struct xnow_owner_stream *stream, const void *data,
                             size_t bytes, const struct xnow_full_received *event)
{
    assert(stream == &owner_stream && data && bytes == event->info.payload_bytes);
    ready_events++;
    return 0;
}

static int owner_prepare_cancel(int reason)
{
    (void)reason;
    stop_requested = owner_control.stop_requested = 1;
    return 0;
}

static int fixture_shared_channel(struct xnow_sd8686_full *radio, unsigned *channel)
{
    (void)radio;
    *channel = 1;
    return 0;
}

static int owner_mode_recheck(void)
{
    parent_checks++;
    return parent_failure || stop_requested ? -1 : 0;
}

static int pairing_queue_snapshot(uint32_t *head, uint32_t *drops)
{
    *head = *drops = 0;
    return 0;
}

int hb_monotonic_millis(unsigned long long *now)
{
    *now = 1000;
    return 0;
}

/* ACTUAL_OWNER_PREPARE */

static void setup(int pairing, int shared)
{
    assert(shared_rx_socket < 0 && !membership_count);
    owner_control = (struct xnow_full_control){0};
    owner_control.endpoint.channel = 1;
    owner_control.local_mac[0] = 2;
    owner_control.local_mac[5] = 9;
    owner_control.shared_channel = shared ? fixture_shared_channel : NULL;
    pairing_listener = pairing;
    stop_requested = 0;
    opens = closes = endpoint_calls = ready_events = 0;
    socket_failure = security_failure = endpoint_failure = 0;
    parent_failure = stop_in_security = stop_in_peer = 0;
    parent_checks = 0;
}

int main(void)
{
    for (int pairing = 0; pairing <= 1; pairing++) {
        for (int shared = 0; shared <= 1; shared++) {
            setup(pairing, shared);
            assert(!owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac));
            assert(endpoint_calls == 1 && ready_events == (unsigned)pairing);
            assert(parent_checks == 1);
            /* Pairing and normal encrypted traffic use the same shared chip. */
            if (membership_count != (unsigned)shared) {
                fprintf(stderr, "RX_MEMBERSHIP_MISSING pairing=%d shared=%d refs=%u\n",
                        pairing, shared, membership_count);
                return 1;
            }
            assert(opens == (unsigned)shared);
            assert(!shared_rx_socket_close() && !membership_count);
            assert(closes == (unsigned)shared);
        }
    }
    for (int pairing = 0; pairing <= 1; pairing++) {
        for (int failure = 1; failure <= 2; failure++) {
            setup(pairing, 1);
            socket_failure = failure;
            int rc = owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac);
            assert(rc == (failure == 1 ? -4101 : -4103));
            assert(!membership_count && !ready_events && shared_rx_socket < 0);
        }
        setup(pairing, 1);
        endpoint_failure = -71;
        assert(owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac) ==
               (pairing ? -1 : -71));
        /* A failed prepare retains the acquired resource for normal drain. */
        assert(membership_count == 1 && !ready_events && shared_rx_socket >= 0);
        assert(!shared_rx_socket_close() && !membership_count);

        setup(pairing, 1);
        parent_failure = 1;
        assert(!owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac));
        assert(stop_requested && owner_control.stop_requested && parent_checks == 1);
        assert(membership_count == 1 && !ready_events);
        assert(!shared_rx_socket_close() && !membership_count);

        setup(pairing, 1);
        stop_in_peer = 1;
        assert(!owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac));
        assert(stop_requested && owner_control.stop_requested && !ready_events);
        assert(membership_count == 1 && parent_checks == 1);
        assert(!shared_rx_socket_close() && !membership_count);
    }
    setup(0, 1);
    security_failure = -72;
    assert(owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac) == -72);
    assert(!endpoint_calls && membership_count == 1 && !ready_events);
    assert(!shared_rx_socket_close() && !membership_count);
    setup(0, 1);
    stop_in_security = 1;
    assert(!owner_prepare(NULL, &owner_control.endpoint, owner_control.local_mac));
    assert(stop_requested && owner_control.stop_requested && !endpoint_calls);
    assert(membership_count == 1 && !ready_events && !parent_checks);
    assert(!shared_rx_socket_close() && !membership_count);

    setup(0, 1);
    uint8_t wrong_address[6] = {2, 9, 9, 9, 9, 9};
    assert(owner_prepare(NULL, &owner_control.endpoint, wrong_address) == -1);
    assert(!opens && !endpoint_calls && !parent_checks && !membership_count);
    puts("REMOTE_RECEIVE_PREPARE_PASS");
    return 0;
}
