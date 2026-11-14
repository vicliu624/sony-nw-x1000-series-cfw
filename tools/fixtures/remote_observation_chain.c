/* Actual service callbacks, worker, sender and local SDK IPC. Media/RF are models. */
#define main unused_service_entry
#include "../../runtime/apps/wireless-remote/service.c"
#undef main
#include "../../runtime/platform/player/managed_channel.h"
#include "../../runtime/platform/player/managed.h"
#include "../../runtime/platform/services/session.h"
#include "../../runtime/apps/wireless-remote/receiver.h"
#include <assert.h>
#include <sys/wait.h>

static unsigned long long schedule_now;
int hb_monotonic_millis(unsigned long long *out) { *out = schedule_now; return 0; }
struct original_timespec { long seconds, nanos; };
extern int observation_clock(int, struct original_timespec *) __asm__("clock_gettime");
static int transport_clock(void *unused, uint64_t *out)
{
    (void)unused;
    struct original_timespec value;
    if (observation_clock(1, &value) || value.seconds < 0 || value.nanos < 0 || value.nanos >= 1000000000)
        return -1;
    *out = (uint64_t)value.seconds * 1000 + (unsigned long)value.nanos / 1000000;
    return 0;
}

static const uint8_t peer[6] = {2, 1, 2, 3, 4, 5}, key[32] = {1};
static struct wr_receiver receiver;
static unsigned transmissions, radio_active, radio_stage, radio_detached, retirement_polls;
static uint32_t radio_request;
int xnow_client_send(struct xnow_client *client, const uint8_t address[6], const void *data,
                     size_t bytes, uint32_t *request)
{
    assert(client == &radio && !memcmp(address, peer, 6));
    if (radio_active) return XNOW_CLIENT_PENDING;
    assert(bytes <= XNOW_CLIENT_PAYLOAD_MAX);
    if (wr_status_frame(data, bytes)) assert(!wr_receiver_accept(&receiver, peer, data, bytes));
    else { struct wr_mode value; assert(!wr_mode_decode(&value, data, bytes, key)); }
    *request = radio_request = ++transmissions;
    radio_active = 1; radio_stage = 0;
    return 0;
}
int xnow_client_step(struct xnow_client *client) { assert(client == &radio); return 0; }
int xnow_client_take(struct xnow_client *client, struct xnow_client_event *event, void *data, size_t bytes)
{
    (void)data; (void)bytes; assert(client == &radio);
    if (!radio_active) return XNOW_CLIENT_AGAIN;
    memset(event, 0, sizeof *event);
    event->request = radio_request;
    if (!radio_stage++) { event->kind = XNOW_CLIENT_ACK; event->operation = 4; }
    else { event->kind = XNOW_CLIENT_TX; memcpy(event->address, peer, 6); radio_active = 0; }
    return 0;
}
int xnow_client_close(struct xnow_client *client)
{
    assert(client == &radio && !radio_detached++);
    client->used = 0;
    return 0;
}
static int model_retired(void *unused) { (void)unused; retirement_polls++; return 0; }

struct backend_control { int action, mode_result, snapshot_result; };
static int backend_mode_result, backend_snapshot_result;
static int backend_snapshot(void *unused, struct xw_player_snapshot *out)
{
    (void)unused;
    if (backend_snapshot_result) return backend_snapshot_result;
    memset(out, 0, sizeof *out);
    out->valid = XW_PF_STATE | XW_PF_TRACK | XW_PF_METADATA | XW_PF_VOLUME;
    out->state = XW_PLAY_PLAYING; out->volume = 10; out->volume_max = 30;
    strcpy(out->track.id.value, "fixture-track");
    out->track.flags = 7;
    strcpy(out->track.title, "Fixture track"); strcpy(out->track.artist, "Artist");
    strcpy(out->track.album, "Album");
    return 0;
}
static int backend_mode(void *unused, uint32_t *native, uint32_t *index)
{
    (void)unused;
    if (backend_mode_result) return backend_mode_result;
    *native = 5; *index = 4; return 0;
}
static int backend_close(void *unused) { (void)unused; assert(!"Borrowed original backend was closed"); return -1; }
static void serve(int sdk, int control)
{
    struct xw_player backend = {0};
    struct xw_session_manager manager = {0}; struct xw_session_handle handle;
    struct xw_managed_player service_player = {0}; struct xw_managed_channel channel = {0};
    struct xw_player_provider provider = {XW_PLAYER_API, 0, 0, backend_snapshot, 0, 0, backend_close};
    uint64_t now;
    assert(!transport_clock(0, &now));
    assert(!xw_player_bind(&backend, &provider) && !xw_sessions_init(&manager, 71, 1));
    assert(!xw_session_open(&manager, 1, 1, &handle));
    assert(!xw_managed_player_bind(&service_player, &manager, handle, &backend));
    assert(!xw_managed_player_mode_bind(&service_player, 0, backend_mode));
    assert(!xw_managed_channel_open(&channel, &service_player, sdk, now));
    for (;;) {
        struct pollfd wait[2] = {{control, POLLIN, 0}, {channel.bound ? channel.fd : -1, POLLIN, 0}};
        assert(poll(wait, 2, 1) >= 0);
        if (wait[0].revents & POLLIN) {
            struct backend_control request;
            assert(read(control, &request, sizeof request) == sizeof request);
            backend_mode_result = request.mode_result;
            backend_snapshot_result = request.snapshot_result;
            if (request.action && channel.bound) assert(xw_managed_channel_close(&channel) == XW_MANAGED_CHANNEL_RELEASED);
            assert(write(control, "A", 1) == 1);
            if (request.action == 2) break;
        }
        assert(!transport_clock(0, &now));
        if (channel.bound) {
            int result = xw_managed_channel_tick(&channel, now);
            assert(!result || result == XW_MANAGED_CHANNEL_RELEASED || result == XW_PLAYER_CLOSED);
        }
    }
    assert(backend.initialized);
    close(control);
    _exit(0);
}

static void configure_backend(int control, int action, int mode_result, int snapshot_result)
{
    struct backend_control request = {action, mode_result, snapshot_result};
    char ack = 0;
    assert(write(control, &request, sizeof request) == sizeof request);
    assert(read(control, &ack, 1) == 1 && ack == 'A');
}
static void run_window(uint64_t begin)
{
    for (unsigned i = 0; i < 30; i++) {
        schedule_now = begin + i * 10;
        assert(wr_worker_step(&worker, schedule_now) == XW_PLAYER_BUSY);
        assert(worker.phase == WR_WORKER_RUNNING && managed.remote.bound && !radio_detached);
    }
    assert(!sender.pending && !radio_active);
}
static void scenario(unsigned kind)
{
    int sdk[2], control[2];
    assert(!socketpair(AF_UNIX, SOCK_STREAM, 0, sdk));
    assert(!socketpair(AF_UNIX, SOCK_DGRAM, 0, control));
    pid_t child = fork(); assert(child >= 0);
    if (!child) { close(sdk[0]); close(control[0]); serve(sdk[1], control[1]); }
    close(sdk[1]); close(control[1]);
    assert(!xw_managed_client_bind(&player, &managed, sdk[0], 71, 1500, &transport_cancel, 0, transport_clock));
    radio.used = 1;
    assert(!wr_sender_init(&sender, &player, &radio, peer, key, 37));
    sender.source_context = &managed; sender.source_alive = source_alive;
    assert(!wr_receiver_pair(&receiver, peer, key, 37));
    assert(!wr_worker_init(&worker, &sender, 0, close_player, model_retired));
    worker.before_sample = sample_mode;
    run_window(100);
    assert(receiver.have_status && receiver.status.state == XW_PLAY_PLAYING && transmissions == 2);
    if (!kind) {
        configure_backend(control[0], 0, XW_PLAYER_BUSY, XW_PLAYER_BUSY);
        run_window(2100);
        assert(receiver.status.valid == 0 && transmissions == 4 && managed.remote.bound);
        configure_backend(control[0], 0, XW_PLAYER_UNAVAILABLE, XW_PLAYER_UNAVAILABLE);
        run_window(4100);
        unsigned quiet = transmissions;
        for (unsigned i = 0; i < 10; i++) run_window(6100 + i * 2000);
        assert(transmissions == quiet);
        configure_backend(control[0], 0, 0, 0);
        run_window(28100);
        assert(receiver.status.state == XW_PLAY_PLAYING && (receiver.status.valid & XW_PF_TRACK));
        assert(!strcmp(receiver.status.id, "fixture-track") && transmissions == quiet + 2);
        wr_worker_stop(&worker); schedule_now = 30100;
        assert(!wr_worker_step(&worker, schedule_now) && worker.phase == WR_WORKER_DONE);
        puts("REMOTE_OBSERVATION_CASE live-unavailable-recovery-no-heartbeat");
    } else {
        configure_backend(control[0], kind == 2 ? 1 : 0, 0, kind == 1 ? XW_PLAYER_IO : 0);
        schedule_now = 2100;
        int result = wr_worker_step(&worker, schedule_now);
        assert(worker.reason == WR_WORKER_STOP_OBSERVATION && !managed.remote.bound && !player.initialized);
        if (kind == 1) {
            assert(!result && worker.phase == WR_WORKER_DONE && worker.last_error == XW_PLAYER_IO);
            puts("REMOTE_OBSERVATION_CASE media-io-stops-with-close-receipt");
        } else {
            assert(result == XW_PLAYER_UNCERTAIN && worker.phase == WR_WORKER_FAULT && worker.player_failure);
            puts("REMOTE_OBSERVATION_CASE transport-eof-is-not-a-live-observation");
        }
    }
    assert(radio_detached == 1 && retirement_polls == 1 && !sender.active);
    configure_backend(control[0], 2, 0, 0); close(control[0]);
    int status = 0; assert(waitpid(child, &status, 0) == child && !status);
    fflush(stdout);
}
int main(void)
{
    for (unsigned i = 0; i < 3; i++) {
        pid_t child = fork(); assert(child >= 0);
        if (!child) { scenario(i); _exit(0); }
        int status = 0; assert(waitpid(child, &status, 0) == child && !status);
    }
    puts("REMOTE_OBSERVATION_CHAIN_PASS");
    return 0;
}
